import time
import uuid

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.models import ApiKey, ModelCatalog, RoutingPool, Transaction, UsageLog, User, UserModel
from app.core.security import hash_api_secret
from app.modules.gateway.routing import routing_capacity

router = APIRouter(prefix="/v1", tags=["OpenAI-compatible Gateway"])


def authenticate_api_key(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> tuple[User, ApiKey]:
    if not authorization.startswith("Bearer "): raise HTTPException(401, "Missing API key")
    raw = authorization.removeprefix("Bearer ").strip()
    key = db.scalar(select(ApiKey).where(ApiKey.secret_hash == hash_api_secret(raw), ApiKey.status == "active"))
    if not key: raise HTTPException(401, "Invalid API key")
    user = db.get(User, key.user_id)
    if not user or user.status != "active": raise HTTPException(403, "Account is inactive")
    return user, key


@router.get("/models")
def available_models(auth: tuple[User, ApiKey] = Depends(authenticate_api_key), db: Session = Depends(get_db)) -> dict:
    user, _ = auth
    items = db.scalars(select(ModelCatalog).join(UserModel).where(UserModel.user_id == user.id, ModelCatalog.enabled.is_(True))).all()
    return {"object": "list", "data": [{"id": item.id, "object": "model", "owned_by": item.provider} for item in items]}


@router.post("/chat/completions")
async def chat_completions(payload: dict, auth: tuple[User, ApiKey] = Depends(authenticate_api_key), db: Session = Depends(get_db)) -> dict:
    user, key = auth; model_id = str(payload.get("model", "")); model = db.get(ModelCatalog, model_id)
    if not model or not model.enabled or not db.get(UserModel, (user.id, model_id)): raise HTTPException(403, "Model is not assigned to this account")
    if user.balance <= 0 or user.token_used >= user.token_quota: raise HTTPException(402, "Balance or token quota exhausted")
    if not settings.nine_router_api_key: raise HTTPException(503, "9Router credentials are not configured")
    pool = db.scalar(select(RoutingPool).where(RoutingPool.model_id == model_id, RoutingPool.enabled.is_(True)))
    lease = await routing_capacity.acquire(pool, user.id) if pool else None
    started = time.perf_counter(); request_id = f"req_{uuid.uuid4().hex[:20]}"
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{settings.nine_router_base_url.rstrip('/')}/chat/completions", json=payload, headers={"Authorization": f"Bearer {settings.nine_router_api_key}", "X-Nexora-User": str(user.id), "X-Nexora-Pool": str(pool.id) if pool else "", "X-Connection-Id": lease.connection_id if lease and lease.connection_id else ""})
        if response.is_error:
            if pool and response.status_code in {429, 500, 502, 503, 504}:
                if lease and lease.connection_id:
                    await routing_capacity.cooldown_connection(lease, pool.cooldown_seconds)
                else:
                    await routing_capacity.cooldown(pool.id, pool.cooldown_seconds)
            raise HTTPException(response.status_code, response.text[:500])
    finally:
        await routing_capacity.release(lease)
    result = response.json(); usage = result.get("usage", {}); input_tokens = int(usage.get("prompt_tokens", 0)); output_tokens = int(usage.get("completion_tokens", 0)); cost = round(input_tokens * model.input_price / 1_000_000 + output_tokens * model.output_price / 1_000_000)
    user.balance = max(0, user.balance - cost); user.token_used += input_tokens + output_tokens; key.last_used = __import__("datetime").datetime.utcnow()
    db.add(UsageLog(user_id=user.id, model_id=model_id, status="success", input_tokens=input_tokens, output_tokens=output_tokens, cost=cost, latency_ms=round((time.perf_counter() - started) * 1000), request_id=request_id)); db.add(Transaction(user_id=user.id, type="debit", amount=cost, description=f"Usage {model_id} / {request_id}")); db.commit()
    return result
