import asyncio
import time
from typing import Any

import httpx

from app.core.config import settings


class TokenXError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class TokenXClient:
    def __init__(self) -> None:
        self._access_token = ""
        self._expires_at = 0.0
        self._gateway_key = ""
        self._gateway_key_expires_at = 0.0
        self._login_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(settings.tokenx_username and settings.tokenx_password)

    async def _login(self, force: bool = False) -> str:
        if not self.configured:
            raise TokenXError(503, "TokenX credentials are not configured")
        if not force and self._access_token and self._expires_at > time.monotonic():
            return self._access_token
        async with self._login_lock:
            if not force and self._access_token and self._expires_at > time.monotonic():
                return self._access_token
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{settings.tokenx_api_base_url.rstrip('/')}/auth/login",
                    json={"username": settings.tokenx_username, "password": settings.tokenx_password},
                )
            if response.is_error:
                raise TokenXError(response.status_code, "TokenX login failed")
            data = response.json()
            token = str(data.get("access_token") or data.get("token") or "")
            if not token:
                raise TokenXError(502, "TokenX login returned no access token")
            self._access_token = token
            self._expires_at = time.monotonic() + 10 * 60
            return token

    async def request(self, method: str, path: str, json: dict | None = None) -> Any:
        token = await self._login()
        url = f"{settings.tokenx_api_base_url.rstrip('/')}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.request(
                method, url, json=json, headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 401:
                token = await self._login(force=True)
                response = await client.request(
                    method, url, json=json, headers={"Authorization": f"Bearer {token}"}
                )
        if response.is_error:
            try:
                body = response.json()
                message = body.get("message") or body.get("detail") or body.get("error")
            except (ValueError, TypeError):
                message = response.text
            raise TokenXError(response.status_code, str(message or "TokenX request failed")[:500])
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def invalidate_gateway_key(self) -> None:
        self._gateway_key = ""
        self._gateway_key_expires_at = 0.0

    async def gateway_api_key(self) -> str:
        if settings.tokenx_api_key:
            return settings.tokenx_api_key
        if self._gateway_key and self._gateway_key_expires_at > time.monotonic():
            return self._gateway_key
        listing = await self.request("GET", "api-keys")
        values = listing if isinstance(listing, list) else next(
            (listing.get(name) for name in ("items", "data", "api_keys", "keys") if isinstance(listing, dict) and isinstance(listing.get(name), list)), []
        )
        active = next((item for item in values if isinstance(item, dict) and item.get("enabled", item.get("active", True)) and item.get("status", "active") not in ("revoked", "disabled")), None)
        if not active:
            raise TokenXError(503, "No active TokenX API key is available")
        key_id = active.get("id") or active.get("uuid")
        if not key_id:
            raise TokenXError(502, "TokenX API key has no identifier")
        secret = await self.request("GET", f"api-keys/{key_id}/secret")
        if isinstance(secret, dict):
            secret = secret.get("secret") or secret.get("key") or secret.get("api_key") or secret.get("token")
        if not isinstance(secret, str) or not secret:
            raise TokenXError(502, "TokenX returned no gateway API key secret")
        self._gateway_key = secret
        self._gateway_key_expires_at = time.monotonic() + 5 * 60
        return secret


tokenx = TokenXClient()
