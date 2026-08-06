import time
import uuid
import json
import math
import codecs
import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.models import (
    ApiKey,
    ModelCatalog,
    RoutingPool,
    Transaction,
    UsageLog,
    User,
    UserModel,
)
from app.core.security import hash_api_secret
from app.modules.gateway.routing import routing_capacity

router = APIRouter(prefix="/v1", tags=["OpenAI-compatible Gateway"])
logger = logging.getLogger(__name__)


def billed_cost(input_tokens: int, output_tokens: int, model: ModelCatalog) -> int:
    raw = (
        input_tokens * model.input_price / 1_000_000
        + output_tokens * model.output_price / 1_000_000
    )
    return max(1, math.ceil(raw))


def reserved_cost(payload: dict, model: ModelCatalog) -> int:
    approximate_input = max(1, math.ceil(len(json.dumps(payload, ensure_ascii=False)) / 4))
    maximum_output = max(
        1, int(payload.get("max_completion_tokens") or payload.get("max_tokens") or 4096)
    )
    estimate = (
        approximate_input * model.input_price / 1_000_000
        + maximum_output * model.output_price / 1_000_000
    )
    return max(1, math.ceil(estimate * 1.25))


def ensure_funded(user: User, payload: dict, model: ModelCatalog) -> None:
    required = reserved_cost(payload, model)
    if user.balance < required:
        raise HTTPException(
            402, f"Insufficient balance. At least {required} VND is required for this request"
        )


def upstream_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = dict(extra or {})
    if settings.nine_router_api_key:
        headers["Authorization"] = f"Bearer {settings.nine_router_api_key}"
    if settings.nine_router_internal_key:
        headers["X-Nexora-Internal-Key"] = settings.nine_router_internal_key
    return headers


def upstream_model_id(model_id: str) -> str:
    if "/" in model_id:
        return model_id
    aliases = {
        "claude-opus-4.8": "ag/claude-opus-4-6-thinking",
        "claude-sonnet-5": "ag/claude-sonnet-4-6",
        "gpt-5.5-high": "cx/gpt-5.5",
    }
    if model_id in aliases:
        return aliases[model_id]
    if model_id.startswith("gpt-"):
        return f"cx/{model_id}"
    if model_id.startswith("gemini-"):
        return f"ag/{model_id}"
    if model_id.startswith("claude-"):
        return f"ag/{model_id}"
    return model_id


def authenticate_api_key(
    authorization: str = Header(default=""),
    x_api_key: str = Header(default="", alias="x-api-key"),
    db: Session = Depends(get_db),
) -> tuple[User, ApiKey]:
    raw = (
        authorization.removeprefix("Bearer ").strip()
        if authorization.startswith("Bearer ")
        else x_api_key.strip()
    )
    if not raw:
        raise HTTPException(401, "Missing API key")
    key = db.scalar(
        select(ApiKey).where(ApiKey.secret_hash == hash_api_secret(raw), ApiKey.status == "active")
    )
    if not key:
        raise HTTPException(401, "Invalid API key")
    user = db.get(User, key.user_id)
    if not user or user.status != "active":
        raise HTTPException(403, "Account is inactive")
    return user, key


@router.get("/models")
def available_models(
    auth: tuple[User, ApiKey] = Depends(authenticate_api_key), db: Session = Depends(get_db)
) -> dict:
    user, _ = auth
    items = db.scalars(
        select(ModelCatalog)
        .join(UserModel)
        .where(UserModel.user_id == user.id, ModelCatalog.enabled.is_(True))
    ).all()
    return {
        "object": "list",
        "data": [{"id": item.id, "object": "model", "owned_by": item.provider} for item in items],
    }


@router.post("/chat/completions")
async def chat_completions(
    payload: dict,
    auth: tuple[User, ApiKey] = Depends(authenticate_api_key),
    db: Session = Depends(get_db),
) -> dict:
    user, key = auth
    model_id = str(payload.get("model", ""))
    model = db.get(ModelCatalog, model_id)
    if not model or not model.enabled or not db.get(UserModel, (user.id, model_id)):
        raise HTTPException(403, "Model is not assigned to this account")
    if user.token_quota > 0 and user.token_used >= user.token_quota:
        raise HTTPException(402, "Token quota exhausted")
    ensure_funded(user, payload, model)
    if not settings.nine_router_api_key and not settings.nine_router_internal_key:
        raise HTTPException(503, "9Router credentials are not configured")
    pool = db.scalar(
        select(RoutingPool).where(RoutingPool.model_id == model_id, RoutingPool.enabled.is_(True))
    )
    lease = await routing_capacity.acquire(pool, user.id) if pool else None
    started = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex[:20]}"
    upstream_payload = {**payload, "model": upstream_model_id(model_id)}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.nine_router_base_url.rstrip('/')}/chat/completions",
                json=upstream_payload,
                headers=upstream_headers(
                    {
                        "X-Nexora-User": str(user.id),
                        "X-Nexora-Pool": str(pool.id) if pool else "",
                        "X-Connection-Id": lease.connection_id
                        if lease and lease.connection_id
                        else "",
                    }
                ),
            )
        if response.is_error:
            if pool and response.status_code in {429, 500, 502, 503, 504}:
                if lease and lease.connection_id:
                    await routing_capacity.cooldown_connection(lease, pool.cooldown_seconds)
                else:
                    await routing_capacity.cooldown(pool.id, pool.cooldown_seconds)
            raise HTTPException(response.status_code, response.text[:500])
    finally:
        await routing_capacity.release(lease)
    result = response.json()
    usage = result.get("usage", {})
    input_tokens = int(usage.get("prompt_tokens", 0))
    output_tokens = int(usage.get("completion_tokens", 0))
    cost = billed_cost(input_tokens, output_tokens, model)
    user.balance -= cost
    user.token_used += input_tokens + output_tokens
    key.last_used = __import__("datetime").datetime.utcnow()
    db.add(
        UsageLog(
            user_id=user.id,
            model_id=model_id,
            status="success",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            latency_ms=round((time.perf_counter() - started) * 1000),
            request_id=request_id,
        )
    )
    db.add(
        Transaction(
            user_id=user.id,
            type="debit",
            amount=cost,
            description=f"Usage {model_id} / {request_id}",
        )
    )
    db.commit()
    return result


@router.post("/messages")
async def anthropic_messages(
    payload: dict,
    auth: tuple[User, ApiKey] = Depends(authenticate_api_key),
    db: Session = Depends(get_db),
    anthropic_version: str = Header(default="2023-06-01"),
    anthropic_beta: str = Header(default=""),
) -> Response:
    user, key = auth
    model_id = str(payload.get("model", ""))
    model = db.get(ModelCatalog, model_id)
    if not model or not model.enabled or not db.get(UserModel, (user.id, model_id)):
        raise HTTPException(403, "Model is not assigned to this account")
    if user.token_quota > 0 and user.token_used >= user.token_quota:
        raise HTTPException(402, "Token quota exhausted")
    ensure_funded(user, payload, model)
    if not settings.nine_router_api_key and not settings.nine_router_internal_key:
        raise HTTPException(503, "9Router credentials are not configured")
    pool = db.scalar(
        select(RoutingPool).where(RoutingPool.model_id == model_id, RoutingPool.enabled.is_(True))
    )
    lease = await routing_capacity.acquire(pool, user.id) if pool else None
    started = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex[:20]}"
    headers = upstream_headers(
        {
            "anthropic-version": anthropic_version,
            "X-Nexora-User": str(user.id),
            "X-Nexora-Pool": str(pool.id) if pool else "",
            "X-Connection-Id": lease.connection_id if lease and lease.connection_id else "",
        }
    )
    if anthropic_beta:
        headers["anthropic-beta"] = anthropic_beta
    client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30))
    request = client.build_request(
        "POST",
        f"{settings.nine_router_base_url.rstrip('/')}/messages",
        json={**payload, "model": upstream_model_id(model_id)},
        headers=headers,
    )
    try:
        upstream = await client.send(request, stream=True)
    except Exception:
        await client.aclose()
        await routing_capacity.release(lease)
        raise
    if upstream.is_error:
        error_body = (await upstream.aread()).decode("utf-8", errors="replace")
        if pool and upstream.status_code in {429, 500, 502, 503, 504}:
            if lease and lease.connection_id:
                await routing_capacity.cooldown_connection(lease, pool.cooldown_seconds)
            else:
                await routing_capacity.cooldown(pool.id, pool.cooldown_seconds)
        await upstream.aclose()
        await client.aclose()
        await routing_capacity.release(lease)
        raise HTTPException(upstream.status_code, error_body[:500])

    content_type = upstream.headers.get("content-type", "application/json")
    if "text/event-stream" in content_type:

        async def relay_stream():
            input_tokens = output_tokens = 0
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            buffer = ""
            terminal_blocks: list[bytes] = []
            event_counts: dict[str, int] = {}
            total_bytes = 0
            saw_message_start = False
            saw_usable_content = False
            saw_error = False
            max_content_index = -1

            def encode_block(block: str) -> bytes:
                return (block.rstrip("\r\n") + "\n\n").encode("utf-8")

            def inspect_block(block: str) -> tuple[str, dict]:
                nonlocal input_tokens, output_tokens
                data_lines = []
                named_event = ""
                for line in block.splitlines():
                    if line.startswith("event:"):
                        named_event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
                if not data_lines:
                    return named_event, {}
                raw_data = "\n".join(data_lines)
                if raw_data == "[DONE]":
                    return named_event or "done", {}
                try:
                    event = json.loads(raw_data)
                except (ValueError, TypeError):
                    return named_event or "malformed", {}
                event_type = str(event.get("type") or named_event or "unknown")
                usage = event.get("usage") or event.get("message", {}).get("usage") or {}
                input_tokens = max(input_tokens, int(usage.get("input_tokens", 0) or 0))
                output_tokens = max(output_tokens, int(usage.get("output_tokens", 0) or 0))
                return event_type, event

            def process_block(block: str) -> bytes | None:
                nonlocal saw_message_start, saw_usable_content, saw_error, max_content_index
                event_type, event = inspect_block(block)
                event_counts[event_type or "comment"] = event_counts.get(event_type or "comment", 0) + 1
                if event_type == "message_start":
                    saw_message_start = True
                elif event_type == "error":
                    saw_error = True
                elif event_type == "content_block_start":
                    max_content_index = max(max_content_index, int(event.get("index", 0) or 0))
                    content_block = event.get("content_block") or {}
                    if content_block.get("type") == "tool_use":
                        saw_usable_content = True
                elif event_type == "content_block_delta":
                    max_content_index = max(max_content_index, int(event.get("index", 0) or 0))
                    delta = event.get("delta") or {}
                    if any(delta.get(field) not in (None, "") for field in ("text", "partial_json", "thinking")):
                        saw_usable_content = True
                encoded = encode_block(block)
                if event_type == "malformed":
                    return None
                if not saw_message_start and event_type not in {"message_start", "error", "ping"}:
                    return None
                if event_type in {"message_delta", "message_stop", "done"}:
                    terminal_blocks.append(encoded)
                    return None
                return encoded

            def fallback_blocks(full_sequence: bool) -> list[bytes]:
                message = "Upstream provider returned no usable content. Please retry this request."
                index = max_content_index + 1
                blocks: list[dict] = []
                if full_sequence:
                    blocks.append(
                        {
                            "type": "message_start",
                            "message": {
                                "id": f"msg_{uuid.uuid4().hex[:20]}",
                                "type": "message",
                                "role": "assistant",
                                "model": model_id,
                                "content": [],
                                "stop_reason": None,
                                "stop_sequence": None,
                                "usage": {"input_tokens": input_tokens, "output_tokens": 0},
                            },
                        }
                    )
                    index = 0
                blocks.extend(
                    [
                        {
                            "type": "content_block_start",
                            "index": index,
                            "content_block": {"type": "text", "text": ""},
                        },
                        {
                            "type": "content_block_delta",
                            "index": index,
                            "delta": {"type": "text_delta", "text": message},
                        },
                        {"type": "content_block_stop", "index": index},
                    ]
                )
                return [
                    encode_block(f"event: {item['type']}\ndata: {json.dumps(item, ensure_ascii=False)}")
                    for item in blocks
                ]

            try:
                async for chunk in upstream.aiter_bytes():
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    buffer += decoder.decode(chunk)
                    while True:
                        lf_pos = buffer.find("\n\n")
                        crlf_pos = buffer.find("\r\n\r\n")
                        positions = [pos for pos in (lf_pos, crlf_pos) if pos >= 0]
                        if not positions:
                            break
                        pos = min(positions)
                        delimiter_length = 4 if buffer.startswith("\r\n\r\n", pos) else 2
                        block, buffer = buffer[:pos], buffer[pos + delimiter_length :]
                        if block:
                            encoded = process_block(block)
                            if encoded:
                                yield encoded
                buffer += decoder.decode(b"", final=True)
                if buffer.strip():
                    encoded = process_block(buffer)
                    if encoded:
                        yield encoded

                if not saw_error:
                    if not saw_message_start or not saw_usable_content:
                        for fallback in fallback_blocks(full_sequence=not saw_message_start):
                            yield fallback
                    if terminal_blocks:
                        for terminal in terminal_blocks:
                            yield terminal
                    else:
                        delta = {
                            "type": "message_delta",
                            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                            "usage": {"output_tokens": output_tokens},
                        }
                        stop = {"type": "message_stop"}
                        yield encode_block(
                            f"event: message_delta\ndata: {json.dumps(delta, ensure_ascii=False)}"
                        )
                        yield encode_block(
                            f"event: message_stop\ndata: {json.dumps(stop, ensure_ascii=False)}"
                        )
                else:
                    for terminal in terminal_blocks:
                        yield terminal
            finally:
                logger.info(
                    "anthropic_stream request_id=%s upstream_bytes=%s events=%s "
                    "message_start=%s usable_content=%s error=%s",
                    request_id,
                    total_bytes,
                    event_counts,
                    saw_message_start,
                    saw_usable_content,
                    saw_error,
                )
                await upstream.aclose()
                await client.aclose()
                await routing_capacity.release(lease)
                cost = billed_cost(input_tokens, output_tokens, model)
                user.balance -= cost
                user.token_used += input_tokens + output_tokens
                key.last_used = __import__("datetime").datetime.utcnow()
                db.add(
                    UsageLog(
                        user_id=user.id,
                        model_id=model_id,
                        status="success",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost,
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        request_id=request_id,
                    )
                )
                db.add(
                    Transaction(
                        user_id=user.id,
                        type="debit",
                        amount=cost,
                        description=f"Usage {model_id} / {request_id}",
                    )
                )
                db.commit()

        response_headers = {
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
        return StreamingResponse(
            relay_stream(),
            status_code=upstream.status_code,
            media_type="text/event-stream",
            headers=response_headers,
        )

    body = await upstream.aread()
    await upstream.aclose()
    await client.aclose()
    await routing_capacity.release(lease)
    try:
        usage = json.loads(body).get("usage", {})
    except (ValueError, TypeError):
        usage = {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    cost = billed_cost(input_tokens, output_tokens, model)
    user.balance -= cost
    user.token_used += input_tokens + output_tokens
    key.last_used = __import__("datetime").datetime.utcnow()
    db.add(
        UsageLog(
            user_id=user.id,
            model_id=model_id,
            status="success",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            latency_ms=round((time.perf_counter() - started) * 1000),
            request_id=request_id,
        )
    )
    db.add(
        Transaction(
            user_id=user.id,
            type="debit",
            amount=cost,
            description=f"Usage {model_id} / {request_id}",
        )
    )
    db.commit()
    return Response(
        content=body, status_code=upstream.status_code, media_type=content_type.split(";")[0]
    )


@router.post("/messages/count_tokens")
async def anthropic_count_tokens(
    payload: dict,
    auth: tuple[User, ApiKey] = Depends(authenticate_api_key),
    db: Session = Depends(get_db),
    anthropic_version: str = Header(default="2023-06-01"),
    anthropic_beta: str = Header(default=""),
) -> Response:
    user, _ = auth
    model_id = str(payload.get("model", ""))
    model = db.get(ModelCatalog, model_id)
    if not model or not model.enabled or not db.get(UserModel, (user.id, model_id)):
        raise HTTPException(403, "Model is not assigned to this account")
    if not settings.nine_router_api_key and not settings.nine_router_internal_key:
        raise HTTPException(503, "9Router credentials are not configured")
    headers = upstream_headers(
        {"anthropic-version": anthropic_version, "X-Nexora-User": str(user.id)}
    )
    if anthropic_beta:
        headers["anthropic-beta"] = anthropic_beta
    async with httpx.AsyncClient(timeout=60) as client:
        upstream = await client.post(
            f"{settings.nine_router_base_url.rstrip('/')}/messages/count_tokens",
            json={**payload, "model": upstream_model_id(model_id)},
            headers=headers,
        )
    if upstream.is_error:
        raise HTTPException(upstream.status_code, upstream.text[:500])
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json").split(";")[0],
    )
