from typing import Any

import httpx

from app.core.config import settings


class NineRouterClient:
    @property
    def api_base_url(self) -> str:
        return settings.nine_router_base_url.rstrip("/")

    @property
    def dashboard_base_url(self) -> str:
        return self.api_base_url.removesuffix("/v1")

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(f"{self.dashboard_base_url}/api/health")
            response.raise_for_status()
            return response.json()

    async def models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.api_base_url}/models", headers=self.gateway_headers)
            response.raise_for_status()
            return response.json().get("data", [])

    async def analytics(self, period: str = "24h") -> tuple[dict[str, Any], list[dict[str, Any]]]:
        async with httpx.AsyncClient(base_url=self.dashboard_base_url, timeout=12) as client:
            login = await client.post("/api/auth/login", json={"password": settings.nine_router_dashboard_password})
            login.raise_for_status()
            stats = await client.get(f"/api/usage/stats?period={period}")
            chart = await client.get(f"/api/usage/chart?period={period}")
            stats.raise_for_status(); chart.raise_for_status()
            return stats.json(), chart.json()

    async def dashboard_get(self, path: str) -> Any:
        return await self.dashboard_request("GET", path)

    async def dashboard_request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(base_url=self.dashboard_base_url, timeout=15) as client:
            headers: dict[str, str] = {}
            if settings.nine_router_internal_key:
                headers["X-Nexora-Internal-Key"] = settings.nine_router_internal_key
            else:
                login = await client.post("/api/auth/login", json={"password": settings.nine_router_dashboard_password})
                login.raise_for_status()
            response = await client.request(method, path, json=payload, headers=headers)
            response.raise_for_status()
            return response.json() if response.content else None

    async def forward(self, endpoint: str, payload: dict[str, Any], timeout: int = 120) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(f"{self.api_base_url}/{endpoint.lstrip('/')}", json=payload, headers=self.gateway_headers)

    @property
    def gateway_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {settings.nine_router_api_key}"}


nine_router = NineRouterClient()
