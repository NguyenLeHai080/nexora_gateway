import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.seed import seed_database
from app.modules.admin.router import router as admin_router
from app.modules.account.router import router as account_router
from app.modules.api_keys.router import router as api_keys_router
from app.modules.auth.router import router as auth_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.models.router import router as models_router
from app.modules.gateway.router import router as gateway_router
from app.modules.wallet.router import router as wallet_router
from app.modules.banking.router import router as banking_router

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
embedded_router_client = httpx.AsyncClient(timeout=120, follow_redirects=False)


@app.middleware("http")
async def proxy_embedded_router_api(request: Request, call_next):
    """Route root-relative API calls from the embedded UI back to 9Router."""
    referer = request.headers.get("referer", "")
    if request.url.path.startswith("/api/") and "/router-embed/" in referer:
        target = f"{settings.nine_router_base_url.removesuffix('/v1')}{request.url.path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        headers = {
            key: value for key, value in request.headers.items()
            if key.lower() not in {"host", "content-length", "connection", "accept-encoding"}
        }
        try:
            upstream = await embedded_router_client.request(request.method, target, headers=headers, content=await request.body())
        except httpx.HTTPError as exc:
            return Response(f"9Router embedded API unavailable: {exc}", status_code=502)
        response_headers = {
            key: value for key, value in upstream.headers.items()
            if key.lower() not in {"content-length", "content-encoding", "transfer-encoding", "connection"}
        }
        return Response(upstream.content, status_code=upstream.status_code, headers=response_headers)
    return await call_next(request)
for router in (auth_router, dashboard_router, wallet_router, api_keys_router, models_router, account_router, admin_router):
    app.include_router(router, prefix="/api")
app.include_router(gateway_router)
app.include_router(banking_router, prefix="/api")


@app.on_event("startup")
def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}
