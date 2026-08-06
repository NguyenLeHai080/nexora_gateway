import time
import uuid
import json
import math

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.models import ApiKey, ModelCatalog, RoutingPool, Transaction, UsageLog, User, UserModel
from app.core.security import hash_api_secret
from app.modules.gateway.routing import routing_capacity

router = APIRouter(prefix="/v1", tags=["OpenAI-compatible Gateway"])


def billed_cost(input_tokens: int, output_tokens: int, model: ModelCatalog) -> int:
    raw = input_tokens * model.input_price / 1_000_000 + output_tokens * model.output_price / 1_000_000
    return max(1, math.ceil(raw))


def reserved_cost(payload: dict, model: ModelCatalog) -> int:
    approximate_input = max(1, math.ceil(len(json.dumps(payload, ensure_ascii=False)) / 4))
    maximum_output = max(1, int(payload.get("max_completion_tokens") or payload.get("max_tokens") or 4096))
    estimate = approximate_input * model.input_price / 1_000_000 + maximum_output * model.output_price / 1_000_000
    return max(1, math.ceil(estimate * 1.25))


def ensure_funded(user: User, payload: dict, model: ModelCatalog) -> None:
    required = reserved_cost(payload, model)
    if user.balance < required:
        raise HTTPException(402, f"Insufficient balance. At least {required} VND is required for this request")


def upstream_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = dict(extra or {})
    if settings.nine_router_api_key:
        headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
    if settings.nine_router_internal_key:
        headers["X-Nexora-Internal-Key"] = settings.nine_router_internal_key
    return headers


def upstream_model_id(model_id: str) -> str:
    if "/" in model_id: return model_id
    aliases = {
        "claude-opus-4.8": "ag/claude-opus-4-6-thinking",
        "claude-sonnet-5": "ag/claude-sonnet-4-6",
        "gpt-5.5-high": "cx/gpt-5.5",
    }
    if model_id in aliases: return aliases[model_id]
    if model_id.startswith("gpt-"): return f"cx/{model_id}"
    if model_id.startswith("gemini-"): return f"ag/{model_id}"
    if model_id.startswith("claude-"): return f"ag/{model_id}"
    return model_id


def authenticate_api_key(authorization: str = Header(default=""), x_api_key: str = Header(default="", alias="x-api-key"), db: Session = Depends(get_db)) -> tuple[User, ApiKey]:
    raw = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else x_api_key.strip()
    if not raw: raise HTTPException(401, "Missing API key")
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
    if user.token_quota > 0 and user.token_used >= user.token_quota: raise HTTPException(402, "Token quota exhausted")
    ensure_funded(user, payload, model)
    if not settings.nine_router_api_key and not settings.nine_router_internal_key: raise HTTPException(503, "9Router credentials are not configured")
    pool = db.scalar(select(RoutingPool).where(RoutingPool.model_id == model_id, RoutingPool.enabled.is_(True)))
    lease = await routing_capacity.acquire(pool, user.id) if pool else None
    started = time.perf_counter(); request_id = f"req_{uuid.uuid4().hex[:20]}"
    upstream_payload = {**payload, "model": upstream_model_id(model_id)}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{settings.nine_router_base_url.rstrip('/')}/chat/completions", json=upstream_payload, headers=upstream_headers({"X-Nexora-User": str(user.id), "X-Nexora-Pool": str(pool.id) if pool else "", "X-Connection-Id": lease.connection_id if lease and lease.connection_id else ""}))
        if response.is_error:
            if pool and response.status_code in {429, 500, 502, 503, 504}:
                if lease and lease.connection_id:
                    await routing_capacity.cooldown_connection(lease, pool.cooldown_seconds)
                else:
                    await routing_capacity.cooldown(pool.id, pool.cooldown_seconds)
            raise HTTPException(response.status_code, response.text[:500])
    finally:
        await routing_capacity.release(lease)
    result = response.json(); usage = result.get("usage", {}); input_tokens = int(usage.get("prompt_tokens", 0)); output_tokens = int(usage.get("completion_tokens", 0)); cost = billed_cost(input_tokens, output_tokens, model)
    user.balance -= cost; user.token_used += input_tokens + output_tokens; key.last_used = __import__("datetime").datetime.utcnow()
    db.add(UsageLog(user_id=user.id, model_id=model_id, status="success", input_tokens=input_tokens, output_tokens=output_tokens, cost=cost, latency_ms=round((time.perf_counter() - started) * 1000), request_id=request_id)); db.add(Transaction(user_id=user.id, type="debit", amount=cost, description=f"Usage {model_id} / {request_id}")); db.commit()
    return result


@router.post("/messages")
async def anthropic_messages(payload: dict, auth: tuple[User, ApiKey] = Depends(authenticate_api_key), db: Session = Depends(get_db), anthropic_version: str = Header(default="2023-06-01"), anthropic_beta: str = Header(default="")) -> Response:
    user, key = auth; model_id = str(payload.get("model", "")); model = db.get(ModelCatalog, model_id)
    if not model or not model.enabled or not db.get(UserModel, (user.id, model_id)): raise HTTPException(403, "Model is not assigned to this account")
    if user.token_quota > 0 and user.token_used >= user.token_quota: raise HTTPException(402, "Token quota exhausted")
    ensure_funded(user, payload, model)
    if not settings.nine_router_api_key and not settings.nine_router_internal_key: raise HTTPException(503, "9Router credentials are not configured")
    pool = db.scalar(select(RoutingPool).where(RoutingPool.model_id == model_id, RoutingPool.enabled.is_(True)))
    lease = await routing_capacity.acquire(pool, user.id) if pool else None
    started = time.perf_counter(); request_id = f"req_{uuid.uuid4().hex[:20]}"
    headers = upstream_headers({"anthropic-version": anthropic_version, "X-Nexora-User": str(user.id), "X-Nexora-Pool": str(pool.id) if pool else "", "X-Connection-Id": lease.connection_id if lease and lease.connection_id else ""})
    if anthropic_beta: headers["anthropic-beta"] = anthropic_beta
    client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30))
    request = client.build_request("POST", f"{settings.nine_router_base_url.rstrip('/')}/messages", json={**payload, "model": upstream_model_id(model_id)}, headers=headers)
    try:
        upstream = await client.send(request, stream=True)
    except Exception:
        await client.aclose()
        await routing_capacity.release(lease)
        raise
    if upstream.is_error:
        error_body = (await upstream.aread()).decode("utf-8", errors="replace")
        if pool and upstream.status_code in {429, 500, 502, 503, 504}:
            if lease and lease.connection_id: await routing_capacity.cooldown_connection(lease, pool.cooldown_seconds)
            else: await routing_capacity.cooldown(pool.id, pool.cooldown_seconds)
        await upstream.aclose(); await client.aclose(); await routing_capacity.release(lease)
        raise HTTPException(upstream.status_code, error_body[:500])

    content_type = upstream.headers.get("content-type", "application/json")
    if "text/event-stream" in content_type:
        async def relay_stream():
            input_tokens = output_tokens = 0
            buffer = ""
            try:
                async for chunk in upstream.aiter_bytes():
                    if not chunk: continue
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.rstrip("\r")
                        if line.startswith("data: "):
                            try: event = json.loads(line[6:])
                            except (ValueError, TypeError): event = {}
                            usage = event.get("usage") or event.get("message", {}).get("usage") or {}
                            input_tokens = max(input_tokens, int(usage.get("input_tokens", 0) or 0))
                            output_tokens = max(output_tokens, int(usage.get("output_tokens", 0) or 0))
                    yield chunk
            finally:
                await upstream.aclose(); await client.aclose(); await routing_capacity.release(lease)
                cost = billed_cost(input_tokens, output_tokens, model)
                user.balance -= cost; user.token_used += input_tokens + output_tokens; key.last_used = __import__("datetime").datetime.utcnow()
                db.add(UsageLog(user_id=user.id, model_id=model_id, status="success", input_tokens=input_tokens, output_tokens=output_tokens, cost=cost, latency_ms=round((time.perf_counter() - started) * 1000), request_id=request_id))
                db.add(Transaction(user_id=user.id, type="debit", amount=cost, description=f"Usage {model_id} / {request_id}")); db.commit()

        response_headers = {
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
        return StreamingResponse(relay_stream(), status_code=upstream.status_code, media_type="text/event-stream", headers=response_headers)

    body = await upstream.aread()
    await upstream.aclose(); await client.aclose(); await routing_capacity.release(lease)
    try: usage = json.loads(body).get("usage", {})
    except (ValueError, TypeError): usage = {}
    input_tokens = int(usage.get("input_tokens", 0) or 0); output_tokens = int(usage.get("output_tokens", 0) or 0)
    cost = billed_cost(input_tokens, output_tokens, model)
    user.balance -= cost; user.token_used += input_tokens + output_tokens; key.last_used = __import__("datetime").datetime.utcnow()
    db.add(UsageLog(user_id=user.id, model_id=model_id, status="success", input_tokens=input_tokens, output_tokens=output_tokens, cost=cost, latency_ms=round((time.perf_counter() - started) * 1000), request_id=request_id)); db.add(Transaction(user_id=user.id, type="debit", amount=cost, description=f"Usage {model_id} / {request_id}")); db.commit()
    return Response(content=body, status_code=upstream.status_code, media_type=content_type.split(";")[0])


@router.post("/messages/count_tokens")
async def anthropic_count_tokens(payload: dict, auth: tuple[User, ApiKey] = Depends(authenticate_api_key), db: Session = Depends(get_db), anthropic_version: str = Header(default="2023-06-01"), anthropic_beta: str = Header(default="")) -> Response:
    user, _ = auth
    model_id = str(payload.get("model", ""))
    model = db.get(ModelCatalog, model_id)
    if not model or not model.enabled or not db.get(UserModel, (user.id, model_id)):
        raise HTTPException(403, "Model is not assigned to this account")
    if not settings.nine_router_api_key and not settings.nine_router_internal_key:
        raise HTTPException(503, "9Router credentials are not configured")
    headers = upstream_headers({"anthropic-version": anthropic_version, "X-Nexora-User": str(user.id)})
    if anthropic_beta: headers["anthropic-beta"] = anthropic_beta
    async with httpx.AsyncClient(timeout=60) as client:
        upstream = await client.post(
            f"{settings.nine_router_base_url.rstrip('/')}/messages/count_tokens",
            json={**payload, "model": upstream_model_id(model_id)},
            headers=headers,
        )
    if upstream.is_error:
        raise HTTPException(upstream.status_code, upstream.text[:500])
    return Response(content=upstream.content, status_code=upstream.status_code, media_type=upstream.headers.get("content-type", "application/json").split(";")[0])
