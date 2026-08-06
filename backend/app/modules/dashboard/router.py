import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.models import Transaction, UsageLog


async def fetch_router_analytics(period: str = "24h") -> tuple[dict, list[dict]] | None:
    if not settings.nine_router_dashboard_password:
        return None
    base = settings.nine_router_base_url.removesuffix("/v1")
    try:
        async with httpx.AsyncClient(base_url=base, timeout=12) as client:
            login = await client.post("/api/auth/login", json={"password": settings.nine_router_dashboard_password})
            login.raise_for_status()
            stats, chart = await __import__("asyncio").gather(client.get(f"/api/usage/stats?period={period}"), client.get(f"/api/usage/chart?period={period}"))
            stats.raise_for_status(); chart.raise_for_status()
            return stats.json(), chart.json()
    except (httpx.HTTPError, ValueError):
        return None

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
async def dashboard(user=Depends(get_current_user), db:Session=Depends(get_db)) -> dict:
    is_admin = user.role == "super_admin"
    transaction_scope = [] if is_admin else [Transaction.user_id == user.id]
    usage_scope = [] if is_admin else [UsageLog.user_id == user.id]
    deposited = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.type == "credit", *transaction_scope)) or 0
    spent = db.scalar(select(func.coalesce(func.sum(UsageLog.cost), 0)).where(*usage_scope)) or 0
    since = datetime.utcnow() - timedelta(hours=24)
    logs = db.scalars(select(UsageLog).where(UsageLog.created_at >= since, *usage_scope)).all()
    requests = len(logs)
    success_requests = sum(1 for item in logs if item.status in {"success", "completed", "200"})
    failed_requests = requests - success_requests
    input_tokens = sum(item.input_tokens for item in logs)
    output_tokens = sum(item.output_tokens for item in logs)
    buckets = [{"time": f"{hour:02}:00", "success": 0, "failed": 0, "tokens": 0, "cost": 0} for hour in range(0, 24, 3)]
    for item in logs:
        bucket = buckets[(item.created_at.hour // 3) % len(buckets)]
        bucket["success" if item.status in {"success", "completed", "200"} else "failed"] += 1
        bucket["tokens"] += item.input_tokens + item.output_tokens
        bucket["cost"] += item.cost

    analytics = await fetch_router_analytics()
    if analytics and is_admin:
        stats, chart_data = analytics
        total = stats.get("totalRequests", 0)
        return {"source": "9router", "balance": deposited, "requests": total, "successRequests": total, "failedRequests": 0, "inputTokens": stats.get("totalPromptTokens", 0), "outputTokens": stats.get("totalCompletionTokens", 0), "tokenQuota": user.token_quota, "tokenUsed": user.token_used, "tokenRemaining": max(0, user.token_quota-user.token_used), "deposited": deposited, "spent": stats.get("totalCost", 0), "chart": [{"time": item.get("label", ""), "success": 0, "failed": 0, "tokens": item.get("tokens", 0), "cost": item.get("cost", 0)} for item in chart_data]}
    return {"source": "local", "balance": deposited if is_admin else user.balance, "requests": requests, "successRequests": success_requests, "failedRequests": failed_requests, "inputTokens": input_tokens, "outputTokens": output_tokens, "tokenQuota": user.token_quota, "tokenUsed": user.token_used, "tokenRemaining": max(0, user.token_quota-user.token_used), "deposited": deposited, "spent": spent, "chart": buckets}
