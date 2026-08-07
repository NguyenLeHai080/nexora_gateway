from datetime import datetime, timedelta, timezone
import secrets

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.models import ModelCatalog, User, UserModel
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.users.repository import serialize_user, users_repository

router = APIRouter(prefix="/auth", tags=["Auth"])


def auth_response(user: User) -> dict:
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": serialize_user(user)}


def provision_social_user(db: Session, name: str, email: str) -> User:
    user = users_repository.find_by_email(db, email)
    if user:
        if user.status != "active": raise HTTPException(403, "Account is inactive")
        return user
    user = User(name=name.strip() or email.split("@")[0], email=email, password_hash=hash_password(secrets.token_urlsafe(32)), role="user", status="active")
    db.add(user); db.flush()
    model_ids = db.scalars(select(ModelCatalog.id).where(ModelCatalog.enabled.is_(True))).all()
    db.add_all(UserModel(user_id=user.id, model_id=model_id) for model_id in model_ids)
    db.commit(); db.refresh(user)
    return user


@router.get("/oauth/google")
def google_oauth_start() -> RedirectResponse:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(503, "Google OAuth is not configured")
    state = jwt.encode({"purpose": "google_oauth", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    callback = f"{settings.oauth_public_url.rstrip('/')}/api/auth/oauth/google/callback"
    query = httpx.QueryParams({"client_id": settings.google_oauth_client_id, "redirect_uri": callback, "response_type": "code", "scope": "openid email profile", "state": state, "prompt": "select_account"})
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@router.get("/oauth/google/callback")
async def google_oauth_callback(code: str, state: str, db: Session = Depends(get_db)) -> RedirectResponse:
    frontend = settings.oauth_public_url.rstrip("/")
    try:
        state_data = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if state_data.get("purpose") != "google_oauth": raise ValueError("Invalid OAuth state")
        callback = f"{frontend}/api/auth/oauth/google/callback"
        async with httpx.AsyncClient(timeout=30) as client:
            token_response = await client.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": settings.google_oauth_client_id, "client_secret": settings.google_oauth_client_secret, "redirect_uri": callback, "grant_type": "authorization_code"})
            token_response.raise_for_status()
            profile_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {token_response.json()['access_token']}"})
            profile_response.raise_for_status()
        profile = profile_response.json()
        if not profile.get("email") or not profile.get("email_verified"): raise ValueError("Google email is not verified")
        user = provision_social_user(db, str(profile.get("name", "")), str(profile["email"]).lower())
        return RedirectResponse(f"{frontend}/login#oauth_token={create_access_token(user.id)}")
    except Exception:
        return RedirectResponse(f"{frontend}/login#oauth_error=google")


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = users_repository.find_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash) or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return auth_response(user)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    email = payload.email.lower().strip()
    if users_repository.find_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password), role="user", status="active")
    db.add(user); db.flush()
    model_ids = db.scalars(select(ModelCatalog.id).where(ModelCatalog.enabled.is_(True))).all()
    db.add_all(UserModel(user_id=user.id, model_id=model_id) for model_id in model_ids)
    db.commit(); db.refresh(user)
    return auth_response(user)


@router.get("/me")
def me(user=Depends(get_current_user)) -> dict:
    return serialize_user(user)
