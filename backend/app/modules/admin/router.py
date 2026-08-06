from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, PositiveInt
import jwt
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
import httpx

from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.core.models import ApiKey, AuditLog, DepositOrder, ModelCatalog, RoutingPool, Transaction, UsageLog, User, UserModel, UserSetting
from app.core.security import hash_api_secret, hash_password
import secrets
from app.modules.users.repository import serialize_user, users_repository
from app.core.config import settings
from app.integrations.nine_router import nine_router
from app.modules.gateway.routing import routing_capacity

router = APIRouter(prefix="/admin", tags=["Super Admin"])


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=8)


class UpdateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=190)
    token_quota: int = Field(ge=0)
    password: str | None = Field(default=None, min_length=8)


class TopUpRequest(BaseModel):
    amount: PositiveInt
    token_amount: PositiveInt | None = None
    description: str = "Admin credit"


class BalanceAdjustmentRequest(BaseModel):
    amount: PositiveInt
    type: str = Field(pattern="^(credit|debit)$")
    token_amount: int = Field(default=0, ge=0)
    description: str = Field(min_length=3, max_length=255)


class TokenAdjustmentRequest(BaseModel):
    operation: str = Field(pattern="^(credit|debit|set)$")
    amount: int = Field(ge=0)
    description: str = Field(min_length=3, max_length=255)


class GrantModelRequest(BaseModel):
    model_id: str


class SetUserModelsRequest(BaseModel):
    model_ids: list[str] = Field(default_factory=list)


class AdminApiKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    quota: int | None = Field(default=None, ge=1)


class ModelUpdateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    provider: str = Field(min_length=2, max_length=60)
    input_price: int = Field(ge=0)
    output_price: int = Field(ge=0)
    enabled: bool


class ModelCreateRequest(ModelUpdateRequest):
    id: str = Field(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9._:/-]+$")


class BulkPricingRequest(BaseModel):
    input_price: int = Field(ge=0)
    output_price: int = Field(ge=0)
    model_ids: list[str] = Field(default_factory=list)


class ProviderCreateRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=120)
    api_key: str = Field(min_length=1)
    priority: int = Field(default=1, ge=1, le=999)


class RoutingPoolRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    model_id: str = Field(min_length=2, max_length=100)
    provider: str = Field(min_length=2, max_length=60)
    strategy: str = Field(default="round-robin", pattern="^(round-robin|fill-first|sticky)$")
    max_concurrency: int = Field(default=10, ge=1, le=1000)
    per_user_concurrency: int = Field(default=2, ge=1, le=100)
    cooldown_seconds: int = Field(default=60, ge=1, le=3600)
    enabled: bool = True
    connection_ids: list[str] = Field(default_factory=list)


def audit(db: Session, actor_id: int, action: str, target: str, details: str = "") -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target=target, details=details))


def model_json(item: ModelCatalog) -> dict:
    return {"id": item.id, "provider": item.provider, "displayName": item.display_name, "inputPrice": item.input_price, "outputPrice": item.output_price, "enabled": item.enabled}


def routing_pool_json(item: RoutingPool) -> dict:
    return {"id": item.id, "name": item.name, "modelId": item.model_id, "provider": item.provider, "strategy": item.strategy, "maxConcurrency": item.max_concurrency, "perUserConcurrency": item.per_user_concurrency, "cooldownSeconds": item.cooldown_seconds, "enabled": item.enabled, "connectionIds": item.connection_ids or [], **routing_capacity.snapshot(item.id)}


def api_key_json(item: ApiKey, secret: str | None = None) -> dict:
    data = {"id": item.id, "name": item.name, "prefix": item.prefix, "status": item.status, "quota": item.quota, "createdAt": item.created_at.strftime("%d/%m/%Y"), "lastUsed": item.last_used.strftime("%d/%m/%Y %H:%M") if item.last_used else None}
    if secret: data["key"] = secret
    return data


@router.get("/routing-pools")
def list_routing_pools(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [routing_pool_json(item) for item in db.scalars(select(RoutingPool).order_by(RoutingPool.name))]


@router.post("/routing-pools", status_code=201)
def create_routing_pool(payload: RoutingPoolRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    if not db.get(ModelCatalog, payload.model_id): raise HTTPException(400, "Model not found")
    if db.scalar(select(RoutingPool).where((RoutingPool.name == payload.name) | (RoutingPool.model_id == payload.model_id))): raise HTTPException(409, "Pool name or model already mapped")
    item = RoutingPool(name=payload.name, model_id=payload.model_id, provider=payload.provider, strategy=payload.strategy, max_concurrency=payload.max_concurrency, per_user_concurrency=payload.per_user_concurrency, cooldown_seconds=payload.cooldown_seconds, enabled=payload.enabled, connection_ids=payload.connection_ids)
    db.add(item); db.flush(); audit(db, admin.id, "routing_pool.created", f"pool:{item.id}", item.model_id); db.commit(); db.refresh(item)
    return routing_pool_json(item)


@router.put("/routing-pools/{pool_id}")
def update_routing_pool(pool_id: int, payload: RoutingPoolRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    item = db.get(RoutingPool, pool_id)
    if not item: raise HTTPException(404, "Routing pool not found")
    duplicate = db.scalar(select(RoutingPool).where(RoutingPool.id != pool_id, ((RoutingPool.name == payload.name) | (RoutingPool.model_id == payload.model_id))))
    if duplicate: raise HTTPException(409, "Pool name or model already mapped")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    audit(db, admin.id, "routing_pool.updated", f"pool:{item.id}", item.model_id); db.commit(); db.refresh(item)
    return routing_pool_json(item)


@router.delete("/routing-pools/{pool_id}", status_code=204)
def delete_routing_pool(pool_id: int, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> None:
    item = db.get(RoutingPool, pool_id)
    if not item: raise HTTPException(404, "Routing pool not found")
    db.delete(item); audit(db, admin.id, "routing_pool.deleted", f"pool:{pool_id}", item.model_id); db.commit()


@router.get("/users")
def list_users(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_user(user) for user in users_repository.list_clients(db)]


@router.post("/users", status_code=201)
def create_user(payload: CreateUserRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    if users_repository.find_by_email(db, payload.email): raise HTTPException(409, "Email already exists")
    user = User(name=payload.name, email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user); db.flush(); audit(db, admin.id, "user.created", f"user:{user.id}", user.email); db.commit(); db.refresh(user)
    return serialize_user(user)


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: UpdateUserRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    duplicate = users_repository.find_by_email(db, payload.email)
    if duplicate and duplicate.id != user.id: raise HTTPException(409, "Email already exists")
    user.name = payload.name.strip(); user.email = payload.email.lower().strip(); user.token_quota = payload.token_quota
    if payload.password: user.password_hash = hash_password(payload.password)
    audit(db, admin.id, "user.updated", f"user:{user.id}", user.email); db.commit()
    return serialize_user(user)


@router.delete("/users/{user_id}")
def archive_user(user_id: int, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    user.status = "archived"; audit(db, admin.id, "user.archived", f"user:{user.id}", user.email); db.commit()
    return serialize_user(user)


@router.delete("/users/{user_id}/permanent", status_code=204)
def permanently_delete_user(user_id: int, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> None:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    if user.status != "archived": raise HTTPException(409, "Archive the account before permanent deletion")
    email = user.email
    for model, condition in (
        (ApiKey, ApiKey.user_id == user_id),
        (UserModel, UserModel.user_id == user_id),
        (UsageLog, UsageLog.user_id == user_id),
        (Transaction, Transaction.user_id == user_id),
        (DepositOrder, DepositOrder.user_id == user_id),
        (UserSetting, UserSetting.user_id == user_id),
    ):
        db.execute(delete(model).where(condition))
    db.delete(user)
    audit(db, admin.id, "user.permanently_deleted", f"user:{user_id}", email)
    db.commit()


@router.patch("/users/{user_id}/status")
def toggle_status(user_id: int, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    user.status = "locked" if user.status == "active" else "active"; audit(db, admin.id, "user.status_changed", f"user:{user.id}", user.status); db.commit()
    return serialize_user(user)


@router.post("/users/{user_id}/topup")
def top_up(user_id: int, payload: TopUpRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    user.balance += payload.amount
    if payload.token_amount: user.token_quota += payload.token_amount
    db.add(Transaction(user_id=user.id, type="credit", amount=payload.amount, description=payload.description)); audit(db, admin.id, "wallet.credited", f"user:{user.id}", str(payload.amount)); db.commit()
    return serialize_user(user)


@router.post("/users/{user_id}/balance")
def adjust_balance(user_id: int, payload: BalanceAdjustmentRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    if payload.type == "debit" and user.balance < payload.amount: raise HTTPException(400, "Insufficient balance")
    direction = 1 if payload.type == "credit" else -1
    token_amount = payload.token_amount
    user.balance += direction * payload.amount
    if token_amount: user.token_quota = max(user.token_used, user.token_quota + direction * token_amount)
    db.add(Transaction(user_id=user.id, type=payload.type, amount=payload.amount, description=payload.description)); audit(db, admin.id, f"wallet.{payload.type}", f"user:{user.id}", f"{payload.amount} VND"); db.commit()
    return serialize_user(user)


@router.post("/users/{user_id}/tokens")
def adjust_tokens(user_id: int, payload: TokenAdjustmentRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    before = user.token_quota
    if payload.operation == "credit":
        user.token_quota += payload.amount
    elif payload.operation == "debit":
        if user.token_quota == 0: raise HTTPException(400, "Unlimited quota cannot be debited; set a finite quota first")
        if user.token_quota - payload.amount < user.token_used: raise HTTPException(400, "Token quota cannot be lower than tokens already used")
        user.token_quota -= payload.amount
    else:
        if payload.amount != 0 and payload.amount < user.token_used: raise HTTPException(400, "Token quota cannot be lower than tokens already used")
        user.token_quota = payload.amount
    audit(db, admin.id, f"tokens.{payload.operation}", f"user:{user.id}", f"{before} -> {user.token_quota}; {payload.description}")
    db.commit(); db.refresh(user)
    return serialize_user(user)


@router.post("/users/{user_id}/models")
def grant_model(user_id: int, payload: GrantModelRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id); model = db.get(ModelCatalog, payload.model_id)
    if not user: raise HTTPException(404, "User not found")
    if not model: raise HTTPException(400, "Model not found")
    if not db.get(UserModel, (user_id, payload.model_id)): db.add(UserModel(user_id=user_id, model_id=payload.model_id)); audit(db, admin.id, "model.granted", f"user:{user_id}", payload.model_id); db.commit()
    db.refresh(user); return serialize_user(user)


@router.put("/users/{user_id}/models")
def set_user_models(user_id: int, payload: SetUserModelsRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    requested_ids = list(dict.fromkeys(payload.model_ids))
    valid_ids = set(db.scalars(select(ModelCatalog.id).where(ModelCatalog.id.in_(requested_ids), ModelCatalog.enabled.is_(True)))) if requested_ids else set()
    unknown_ids = [model_id for model_id in requested_ids if model_id not in valid_ids]
    if unknown_ids: raise HTTPException(400, f"Unknown or disabled models: {', '.join(unknown_ids)}")
    db.execute(delete(UserModel).where(UserModel.user_id == user_id))
    db.add_all(UserModel(user_id=user_id, model_id=model_id) for model_id in requested_ids)
    audit(db, admin.id, "models.replaced", f"user:{user_id}", f"{len(requested_ids)} models")
    db.commit(); db.refresh(user)
    return serialize_user(user)


@router.get("/users/{user_id}/api-keys")
def admin_list_api_keys(user_id: int, _: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> list[dict]:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    return [api_key_json(item) for item in db.scalars(select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc()))]


@router.post("/users/{user_id}/api-keys", status_code=201)
def admin_create_api_key(user_id: int, payload: AdminApiKeyRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    user = users_repository.get(db, user_id)
    if not user or user.role != "user": raise HTTPException(404, "User not found")
    raw = f"nx-{secrets.token_urlsafe(28)}"
    item = ApiKey(user_id=user_id, name=payload.name.strip(), prefix=raw[:14], secret_hash=hash_api_secret(raw), quota=payload.quota)
    db.add(item); db.flush(); audit(db, admin.id, "api_key.created", f"user:{user_id}/key:{item.id}", item.name); db.commit(); db.refresh(item)
    return api_key_json(item, raw)


@router.put("/users/{user_id}/api-keys/{key_id}")
def admin_update_api_key(user_id: int, key_id: int, payload: AdminApiKeyRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    if not item: raise HTTPException(404, "API key not found")
    item.name = payload.name.strip(); item.quota = payload.quota; audit(db, admin.id, "api_key.updated", f"user:{user_id}/key:{key_id}", item.name); db.commit()
    return api_key_json(item)


@router.patch("/users/{user_id}/api-keys/{key_id}/toggle")
def admin_toggle_api_key(user_id: int, key_id: int, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    if not item: raise HTTPException(404, "API key not found")
    item.status = "disabled" if item.status == "active" else "active"; audit(db, admin.id, "api_key.status", f"user:{user_id}/key:{key_id}", item.status); db.commit()
    return api_key_json(item)


@router.delete("/users/{user_id}/api-keys/{key_id}", status_code=204)
def admin_delete_api_key(user_id: int, key_id: int, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> None:
    item = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    if not item: raise HTTPException(404, "API key not found")
    db.delete(item); audit(db, admin.id, "api_key.deleted", f"user:{user_id}/key:{key_id}", item.name); db.commit()


@router.delete("/users/{user_id}/models/{model_id:path}")
def revoke_model(user_id: int, model_id: str, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    item = db.get(UserModel, (user_id, model_id))
    if not item: raise HTTPException(404, "Entitlement not found")
    db.delete(item); audit(db, admin.id, "model.revoked", f"user:{user_id}", model_id); db.commit()
    user = users_repository.get(db, user_id); db.refresh(user); return serialize_user(user)


@router.get("/finance")
def finance(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    revenue = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.type == "credit")) or 0
    spent = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.type == "debit")) or 0
    gateway_cost = int(spent * .62)
    return {"revenue": revenue, "gatewayCost": gateway_cost, "profit": spent - gateway_cost, "pending": 0}


@router.get("/transactions")
def all_transactions(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Transaction, User).join(User, User.id == Transaction.user_id).order_by(Transaction.created_at.desc()).limit(500)).all()
    return [{"id": tx.id, "userId": user.id, "userName": user.name, "userEmail": user.email, "type": tx.type, "amount": tx.amount, "description": tx.description, "createdAt": tx.created_at.strftime("%d/%m/%Y %H:%M")} for tx, user in rows]


@router.get("/router/models")
def router_models(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [model_json(item) for item in db.scalars(select(ModelCatalog).order_by(ModelCatalog.provider, ModelCatalog.display_name))]


@router.post("/router/models/bulk-pricing")
def bulk_model_pricing(payload: BulkPricingRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    query = select(ModelCatalog)
    if payload.model_ids:
        query = query.where(ModelCatalog.id.in_(payload.model_ids))
    items = db.scalars(query).all()
    for item in items:
        item.input_price = payload.input_price
        item.output_price = payload.output_price
    audit(db, admin.id, "models.bulk_pricing", "model_catalog", f"{len(items)} models: {payload.input_price}/{payload.output_price}")
    db.commit()
    return {"updated": len(items), "inputPrice": payload.input_price, "outputPrice": payload.output_price}


@router.post("/router/models", status_code=201)
def create_model(payload: ModelCreateRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    if db.get(ModelCatalog, payload.id): raise HTTPException(409, "Model already exists")
    model = ModelCatalog(id=payload.id, display_name=payload.display_name, provider=payload.provider, input_price=payload.input_price, output_price=payload.output_price, enabled=payload.enabled)
    db.add(model); audit(db, admin.id, "model.created", f"model:{model.id}"); db.commit()
    return model_json(model)


@router.get("/router/status")
async def router_status(_: User = Depends(require_super_admin)) -> dict:
    health_url = settings.nine_router_base_url.removesuffix("/v1") + "/api/health"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(health_url)
        return {"connected": response.is_success, "baseUrl": settings.nine_router_public_url, "health": response.json() if response.is_success else response.text[:200]}
    except httpx.HTTPError as exc:
        return {"connected": False, "baseUrl": settings.nine_router_public_url, "error": str(exc)}


@router.get("/router/connections")
async def router_connections(_: User = Depends(require_super_admin)) -> dict:
    try:
        payload = await nine_router.dashboard_get("/api/providers")
        connections = payload.get("connections", [])
        return {"connections": [{"id": item.get("id"), "provider": item.get("provider"), "name": item.get("name") or item.get("email") or "Unnamed", "email": item.get("email"), "authType": item.get("authType"), "priority": item.get("priority", 0), "isActive": item.get("isActive", False), "testStatus": item.get("testStatus", "unknown"), "lastUsedAt": item.get("lastUsedAt"), "lastError": item.get("lastError")} for item in connections]}
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Cannot load 9Router connections: {exc}") from exc


@router.get("/router/provider-options")
async def router_provider_options(_: User = Depends(require_super_admin)) -> dict:
    try:
        return await nine_router.dashboard_get("/api/providers/options")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Cannot load provider catalog from 9Router: {exc}") from exc


@router.post("/router/provider-wizard")
def router_provider_wizard(payload: dict, _: User = Depends(require_super_admin)) -> dict:
    provider = str(payload.get("provider", "")).strip()
    now = datetime.now(timezone.utc)
    token = jwt.encode({
        "iss": "nexora",
        "aud": "9router-provider-wizard",
        "purpose": "provider:manage",
        "provider": provider,
        "iat": now,
        "exp": now + timedelta(minutes=2),
    }, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    router_origin = settings.nine_router_public_url.removesuffix("/v1").rstrip("/")
    return {"url": f"{router_origin}/api/nexora/provider-wizard?{urlencode({'token': token})}", "expiresIn": 120}


@router.post("/router/connections", status_code=201)
async def create_router_connection(payload: ProviderCreateRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    try:
        result = await nine_router.dashboard_request("POST", "/api/providers", {
            "provider": payload.provider.strip(),
            "name": payload.name.strip(),
            "apiKey": payload.api_key,
            "priority": payload.priority,
        })
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("error", exc.response.text[:300])
        except ValueError:
            detail = exc.response.text[:300]
        raise HTTPException(400, f"9Router rejected provider: {detail}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Cannot create 9Router connection: {exc}") from exc
    audit(db, admin.id, "router.connection_created", f"provider:{payload.provider}", payload.name); db.commit()
    return result


@router.delete("/router/connections/{connection_id}")
async def delete_router_connection(connection_id: str, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    try:
        result = await nine_router.dashboard_request("DELETE", f"/api/providers/{connection_id}")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Cannot delete 9Router connection: {exc}") from exc
    audit(db, admin.id, "router.connection_deleted", f"connection:{connection_id}"); db.commit()
    return result


@router.patch("/router/connections/{connection_id}/status")
async def update_router_connection_status(connection_id: str, payload: dict, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    is_active = bool(payload.get("is_active"))
    try:
        result = await nine_router.dashboard_request("PUT", f"/api/providers/{connection_id}", {"isActive": is_active})
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Cannot update 9Router connection: {exc}") from exc
    audit(db, admin.id, "router.connection_status", f"connection:{connection_id}", str(is_active)); db.commit()
    return result


@router.post("/router/connections/{connection_id}/test")
async def test_router_connection(connection_id: str, _: User = Depends(require_super_admin)) -> dict:
    try:
        return await nine_router.dashboard_request("POST", f"/api/providers/{connection_id}/test")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"9Router connection test failed: {exc}") from exc


@router.post("/router/sync")
async def sync_router_models(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    try:
        upstream = await nine_router.models()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"9Router models sync failed: {exc}") from exc
    synced = 0
    for item in upstream:
        model_id = item.get("id")
        if not model_id: continue
        model = db.get(ModelCatalog, model_id)
        if not model:
            provider = str(item.get("owned_by", model_id.split("/")[0])).title()
            model = ModelCatalog(id=model_id, provider=provider, display_name=model_id.split("/")[-1], input_price=1, output_price=1, enabled=True)
            db.add(model); synced += 1
    db.commit()
    return {"upstreamCount": len(upstream), "newModels": synced}


@router.patch("/router/models/{model_id:path}")
def update_model(model_id: str, payload: ModelUpdateRequest, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    model = db.get(ModelCatalog, model_id)
    if not model: raise HTTPException(404, "Model not found")
    model.display_name = payload.display_name; model.provider = payload.provider; model.input_price = payload.input_price; model.output_price = payload.output_price; model.enabled = payload.enabled
    audit(db, admin.id, "model.updated", f"model:{model_id}"); db.commit()
    return model_json(model)


@router.delete("/router/models/{model_id:path}", status_code=204)
def delete_model(model_id: str, admin: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> None:
    model = db.get(ModelCatalog, model_id)
    if not model: raise HTTPException(404, "Model not found")
    if db.scalar(select(func.count()).select_from(UserModel).where(UserModel.model_id == model_id)):
        raise HTTPException(409, "Revoke this model from all users before deleting")
    db.delete(model); audit(db, admin.id, "model.deleted", f"model:{model_id}"); db.commit()


@router.get("/audit-logs")
def audit_logs(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(300)).all()
    return [{"id": item.id, "actorId": item.actor_id, "action": item.action, "target": item.target, "details": item.details, "createdAt": item.created_at.strftime("%d/%m/%Y %H:%M:%S")} for item in rows]
