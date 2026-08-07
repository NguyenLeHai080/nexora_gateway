import asyncio
import time
from dataclasses import dataclass

from fastapi import HTTPException


@dataclass
class Lease:
    pool_id: int
    user_id: int
    connection_id: str | None = None


class RoutingCapacity:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pool_active: dict[int, int] = {}
        self._user_active: dict[tuple[int, int], int] = {}
        self._cooldown_until: dict[int, float] = {}
        self._connection_active: dict[str, int] = {}
        self._connection_cooldown_until: dict[str, float] = {}
        self._round_robin_cursor: dict[int, int] = {}
        self._sticky_connection: dict[tuple[int, int], str] = {}

    async def acquire(self, pool, user_id: int) -> Lease:
        async with self._lock:
            remaining = self._cooldown_until.get(pool.id, 0) - time.monotonic()
            if remaining > 0:
                raise HTTPException(503, f"Routing pool is cooling down; retry in {max(1, round(remaining))}s")
            active = self._pool_active.get(pool.id, 0)
            user_key = (pool.id, user_id)
            user_active = self._user_active.get(user_key, 0)
            if active >= pool.max_concurrency:
                raise HTTPException(429, "Routing pool is at maximum concurrency")
            if user_active >= pool.per_user_concurrency:
                raise HTTPException(429, "User concurrency limit reached for this model")
            connection_id = self._select_connection(pool, user_id)
            if pool.connection_ids and not connection_id:
                raise HTTPException(429, "All provider accounts in this pool are busy or cooling down")
            self._pool_active[pool.id] = active + 1
            self._user_active[user_key] = user_active + 1
            if connection_id:
                self._connection_active[connection_id] = self._connection_active.get(connection_id, 0) + 1
                self._sticky_connection[user_key] = connection_id
            return Lease(pool.id, user_id, connection_id)

    def _select_connection(self, pool, user_id: int) -> str | None:
        ids = list(dict.fromkeys(pool.connection_ids or []))
        now = time.monotonic()
        available = [item for item in ids if self._connection_active.get(item, 0) == 0 and self._connection_cooldown_until.get(item, 0) <= now]
        if not available:
            return None
        if pool.strategy == "sticky":
            previous = self._sticky_connection.get((pool.id, user_id))
            if previous in available:
                return previous
        if pool.strategy == "fill-first":
            return available[0]
        cursor = self._round_robin_cursor.get(pool.id, 0) % len(ids)
        for offset in range(len(ids)):
            candidate = ids[(cursor + offset) % len(ids)]
            if candidate in available:
                self._round_robin_cursor[pool.id] = (ids.index(candidate) + 1) % len(ids)
                return candidate
        return None

    async def release(self, lease: Lease | None) -> None:
        if not lease:
            return
        async with self._lock:
            self._pool_active[lease.pool_id] = max(0, self._pool_active.get(lease.pool_id, 1) - 1)
            key = (lease.pool_id, lease.user_id)
            self._user_active[key] = max(0, self._user_active.get(key, 1) - 1)
            if lease.connection_id:
                self._connection_active[lease.connection_id] = max(0, self._connection_active.get(lease.connection_id, 1) - 1)

    async def cooldown(self, pool_id: int, seconds: int) -> None:
        async with self._lock:
            self._cooldown_until[pool_id] = max(self._cooldown_until.get(pool_id, 0), time.monotonic() + seconds)

    async def cooldown_connection(self, lease: Lease | None, seconds: int) -> None:
        if not lease or not lease.connection_id:
            return
        async with self._lock:
            self._connection_cooldown_until[lease.connection_id] = max(self._connection_cooldown_until.get(lease.connection_id, 0), time.monotonic() + seconds)

    def snapshot(self, pool_id: int) -> dict:
        return {"active": self._pool_active.get(pool_id, 0), "cooldownRemaining": max(0, round(self._cooldown_until.get(pool_id, 0) - time.monotonic()))}


routing_capacity = RoutingCapacity()
