import httpx
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.dependencies import get_current_user


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
async def dashboard(user=Depends(get_current_user)) -> dict:
    analytics = await fetch_router_analytics()
    if analytics:
        stats, chart_data = analytics
        total = stats.get("totalRequests", 0)
        return {"source": "9router", "balance": user.balance, "requests": total, "successRequests": total, "failedRequests": 0, "inputTokens": stats.get("totalPromptTokens", 0), "outputTokens": stats.get("totalCompletionTokens", 0), "deposited": user.balance, "spent": stats.get("totalCost", 0), "chart": [{"time": item.get("label", ""), "success": 0, "failed": 0, "tokens": item.get("tokens", 0), "cost": item.get("cost", 0)} for item in chart_data]}
    is_admin = user.role == "super_admin"
    multiplier = 10 if is_admin else 1
    chart = [
        {"time": f"{hour:02}:00", "success": (420 + (hour % 5) * 72) * multiplier, "failed": (8 + hour % 4) * multiplier, "tokens": (18_000 + hour * 950) * multiplier, "cost": 7000 + hour * 500}
        for hour in range(0, 24, 3)
    ]
    return {"source": "fallback", "balance": 12_450_000 if is_admin else user.balance, "requests": 13056 * multiplier, "successRequests": 12885 * multiplier, "failedRequests": 83 * multiplier, "inputTokens": 1_448_298 * multiplier, "outputTokens": 4384 * multiplier, "deposited": 18_850_000 if is_admin else 1_121_500, "spent": 6_400_000 if is_admin else 631_500, "chart": chart}
