from datetime import datetime, timedelta
from typing import Any, Literal
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.core.models import AuditLog, BankAccount, BankQrImage, ModelCatalog, RoutingPool, TokenXFundingAllocation, UsageLog, User
from app.integrations.tokenx import tokenx
from app.integrations.tokenx.client import TokenXError

router = APIRouter(prefix="/admin/tokenx", tags=["TokenX Integration"])


class TokenXApiKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class TokenXApiKeyUpdate(BaseModel):
    status: Literal["active", "disabled", "revoked"]


class TokenXQuotaModeUpdate(BaseModel):
    mode: Literal["limited", "unlimited"]


class TokenXQuotaAdjustment(BaseModel):
    amount: int = Field(ne=0)
    description: str = Field(min_length=3, max_length=200)


class TokenXPoolRequest(BaseModel):
    model_id: str = Field(min_length=2, max_length=100)
    display_name: str = Field(min_length=2, max_length=120)
    input_price: int = Field(ge=0)
    output_price: int = Field(ge=0)
    max_concurrency: int = Field(default=10, ge=1, le=1000)
    per_user_concurrency: int = Field(default=2, ge=1, le=100)
    cooldown_seconds: int = Field(default=60, ge=1, le=3600)


def tokenx_error(exc: TokenXError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


def redact(value: Any) -> Any:
    sensitive = {"access_token", "refresh_token", "secret", "password", "api_key", "key"}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {
            key: ("***" if key.lower() in sensitive and item else redact(item))
            for key, item in value.items()
        }
    return value


def find_number(value: Any, names: set[str]) -> float | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in names and isinstance(item, (int, float)):
                return float(item)
        for item in value.values():
            found = find_number(item, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_number(item, names)
            if found is not None:
                return found
    return None


def accuracy(local_value: float, upstream_value: float | None) -> float | None:
    if upstream_value is None:
        return None
    denominator = max(1.0, abs(local_value), abs(upstream_value))
    return round(max(0.0, 100.0 - abs(local_value - upstream_value) / denominator * 100.0), 2)


async def remote_snapshot() -> dict:
    endpoints = {
        "account": ("GET", "auth/me"),
        "summary": ("GET", "dashboard/summary"),
        "wallet": ("GET", "wallet"),
        "transactions": ("GET", "wallet/transactions?page=1&page_size=20"),
        "apiKeys": ("GET", "api-keys"),
        "requestLogs": ("GET", "request-logs?page=1&page_size=100"),
    }
    result: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key, (method, path) in endpoints.items():
        try:
            result[key] = redact(await tokenx.request(method, path))
        except TokenXError as exc:
            errors[key] = str(exc)
    result["errors"] = errors
    return result


async def remote_resource(path: str) -> Any:
    if not tokenx.configured:
        raise HTTPException(503, "TokenX credentials are not configured")
    try:
        return redact(await tokenx.request("GET", path))
    except TokenXError as exc:
        raise tokenx_error(exc) from exc


@router.get("/api-keys")
async def list_api_keys(_: User = Depends(require_super_admin)) -> Any:
    return await remote_resource("api-keys")


@router.get("/transactions")
async def list_transactions(_: User = Depends(require_super_admin)) -> Any:
    return await remote_resource("wallet/transactions?page=1&page_size=100")


@router.get("/request-logs")
async def list_request_logs(_: User = Depends(require_super_admin)) -> Any:
    return await remote_resource("request-logs?page=1&page_size=200")


@router.get("/pricing-rules")
async def list_pricing_rules(_: User = Depends(require_super_admin)) -> Any:
    return await remote_resource("pricing-rules")


@router.get("/funding")
def funding(_: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict:
    payee_row = db.execute(
        select(BankAccount, BankQrImage)
        .join(BankQrImage, BankQrImage.bank_account_id == BankAccount.id)
        .where(BankAccount.enabled.is_(False))
        .order_by(BankQrImage.updated_at.desc())
    ).first()
    pending = db.scalar(
        select(func.coalesce(func.sum(TokenXFundingAllocation.reserve_amount), 0))
        .where(TokenXFundingAllocation.status == "reserved")
    ) or 0
    username = re.sub(r"[^a-zA-Z0-9]", "", settings.tokenx_username).lower()
    payment_content = f"tkx{username}" if username else ""
    if not payee_row:
        return {"configured": False, "pendingAmount": pending, "paymentContent": payment_content}
    bank, _ = payee_row
    qr_url = (
        f"https://img.vietqr.io/image/{quote(bank.bank_code)}-{quote(bank.account_number)}-compact2.png"
        f"?amount={pending}&addInfo={quote(payment_content)}&accountName={quote(bank.account_name)}"
    )
    return {
        "configured": True,
        "pendingAmount": pending,
        "paymentContent": payment_content,
        "qrUrl": qr_url,
        "bank": {
            "id": bank.id,
            "bankCode": bank.bank_code,
            "bankName": bank.bank_name,
            "accountNumber": bank.account_number,
            "accountName": bank.account_name,
        },
    }


@router.get("/overview")
async def overview(
    _: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> dict:
    if not tokenx.configured:
        return {
            "configured": False,
            "gatewayConfigured": bool(settings.tokenx_api_key),
            "error": "Set TOKENX_USERNAME and TOKENX_PASSWORD on the server",
        }
    try:
        remote = await remote_snapshot()
    except TokenXError as exc:
        raise tokenx_error(exc) from exc
    since = datetime.utcnow() - timedelta(hours=24)
    local = db.execute(
        select(
            func.count(UsageLog.id),
            func.coalesce(func.sum(UsageLog.input_tokens), 0),
            func.coalesce(func.sum(UsageLog.output_tokens), 0),
            func.coalesce(func.sum(UsageLog.cost), 0),
        ).where(UsageLog.created_at >= since, UsageLog.model_id.like("tx/%"))
    ).one()
    local_tokens = int(local[1]) + int(local[2])
    summary = remote.get("summary") or {}
    remote_tokens = find_number(summary, {"total_tokens", "tokens", "token_count"})
    remote_cost = find_number(summary, {"total_cost", "cost", "spent", "usage_cost"})
    return {
        "configured": True,
        "gatewayConfigured": bool(settings.tokenx_api_key),
        **remote,
        "reconciliation": {
            "windowHours": 24,
            "localRequests": int(local[0]),
            "localInputTokens": int(local[1]),
            "localOutputTokens": int(local[2]),
            "localTokens": local_tokens,
            "localRevenue": int(local[3]),
            "upstreamTokens": remote_tokens,
            "upstreamCost": remote_cost,
            "tokenAccuracyPercent": accuracy(local_tokens, remote_tokens),
            "grossMargin": None if remote_cost is None else round(int(local[3]) - remote_cost, 2),
        },
    }


@router.post("/api-keys", status_code=201)
async def create_api_key(
    payload: TokenXApiKeyRequest,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Any:
    try:
        result = await tokenx.request("POST", "api-keys", {"name": payload.name})
    except TokenXError as exc:
        raise tokenx_error(exc) from exc
    tokenx.invalidate_gateway_key()
    db.add(AuditLog(actor_id=admin.id, action="tokenx.api_key.created", target="tokenx", details=payload.name))
    db.commit()
    return result


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> None:
    try:
        await tokenx.request("PATCH", f"api-keys/{key_id}", {"status": "revoked"})
    except TokenXError as exc:
        raise tokenx_error(exc) from exc
    tokenx.invalidate_gateway_key()
    db.add(AuditLog(actor_id=admin.id, action="tokenx.api_key.revoked", target=f"tokenx-key:{key_id}"))
    db.commit()


@router.patch("/api-keys/{key_id}")
async def update_api_key(
    key_id: str,
    payload: TokenXApiKeyUpdate,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Any:
    try:
        result = await tokenx.request("PATCH", f"api-keys/{key_id}", {"status": payload.status})
    except TokenXError as exc:
        raise tokenx_error(exc) from exc
    tokenx.invalidate_gateway_key()
    db.add(AuditLog(actor_id=admin.id, action="tokenx.api_key.status", target=f"tokenx-key:{key_id}", details=payload.status))
    db.commit()
    return result


@router.patch("/api-keys/{key_id}/quota-mode")
async def update_api_key_quota_mode(
    key_id: str,
    payload: TokenXQuotaModeUpdate,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Any:
    try:
        result = await tokenx.request("PATCH", f"api-keys/{key_id}/quota-mode", {"mode": payload.mode})
    except TokenXError as exc:
        raise tokenx_error(exc) from exc
    db.add(AuditLog(actor_id=admin.id, action="tokenx.api_key.quota_mode", target=f"tokenx-key:{key_id}", details=payload.mode))
    db.commit()
    return result


@router.post("/api-keys/{key_id}/quota-adjustments")
async def adjust_api_key_quota(
    key_id: str,
    payload: TokenXQuotaAdjustment,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Any:
    try:
        result = await tokenx.request(
            "POST",
            f"api-keys/{key_id}/quota-adjustments",
            {"amount": str(payload.amount), "description": payload.description},
        )
    except TokenXError as exc:
        raise tokenx_error(exc) from exc
    db.add(AuditLog(actor_id=admin.id, action="tokenx.api_key.quota_adjusted", target=f"tokenx-key:{key_id}", details=f"{payload.amount}: {payload.description}"))
    db.commit()
    return result


@router.post("/pools", status_code=201)
def create_or_update_pool(
    payload: TokenXPoolRequest,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> dict:
    public_model_id = payload.model_id if payload.model_id.startswith("tx/") else f"tx/{payload.model_id}"
    model = db.get(ModelCatalog, public_model_id)
    if not model:
        model = ModelCatalog(
            id=public_model_id,
            provider="tokenx",
            display_name=payload.display_name,
            input_price=payload.input_price,
            output_price=payload.output_price,
            enabled=True,
        )
        db.add(model)
    else:
        model.provider = "tokenx"
        model.display_name = payload.display_name
        model.input_price = payload.input_price
        model.output_price = payload.output_price
        model.enabled = True
    pool = db.scalar(select(RoutingPool).where(RoutingPool.model_id == public_model_id))
    if not pool:
        pool = RoutingPool(name=f"TokenX - {payload.display_name}", model_id=public_model_id, provider="tokenx")
        db.add(pool)
    pool.provider = "tokenx"
    pool.strategy = "round-robin"
    pool.max_concurrency = payload.max_concurrency
    pool.per_user_concurrency = payload.per_user_concurrency
    pool.cooldown_seconds = payload.cooldown_seconds
    pool.enabled = True
    pool.connection_ids = []
    db.flush()
    db.add(AuditLog(actor_id=admin.id, action="tokenx.pool.mapped", target=f"pool:{pool.id}", details=public_model_id))
    db.commit()
    return {"id": pool.id, "modelId": public_model_id, "provider": pool.provider, "enabled": pool.enabled}
