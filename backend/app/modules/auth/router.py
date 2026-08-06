from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.modules.auth.schemas import LoginRequest
from app.modules.users.repository import serialize_user, users_repository

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = users_repository.find_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash) or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": serialize_user(user)}


@router.get("/me")
def me(user=Depends(get_current_user)) -> dict:
    return serialize_user(user)
