from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.models import UsageLog, UserSetting
from app.core.security import hash_password, verify_password

router = APIRouter(tags=["Account"])


class SettingsRequest(BaseModel):
    telegram_enabled: bool
    telegram_chat_id: str = Field(max_length=100)
    low_balance_threshold: int = Field(ge=0)


class PasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


def get_or_create_settings(db: Session, user_id: int) -> UserSetting:
    item = db.get(UserSetting, user_id)
    if not item:
        item = UserSetting(user_id=user_id); db.add(item); db.commit(); db.refresh(item)
    return item


@router.get("/settings")
def get_settings(user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = get_or_create_settings(db, user.id)
    return {"telegramEnabled": item.telegram_enabled, "telegramChatId": item.telegram_chat_id, "lowBalanceThreshold": item.low_balance_threshold}


@router.put("/settings")
def update_settings(payload: SettingsRequest, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = get_or_create_settings(db, user.id); item.telegram_enabled = payload.telegram_enabled; item.telegram_chat_id = payload.telegram_chat_id; item.low_balance_threshold = payload.low_balance_threshold; db.commit()
    return {"telegramEnabled": item.telegram_enabled, "telegramChatId": item.telegram_chat_id, "lowBalanceThreshold": item.low_balance_threshold}


@router.post("/profile/change-password", status_code=204)
def change_password(payload: PasswordRequest, user=Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    if not verify_password(payload.current_password, user.password_hash): raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password); db.commit()


@router.get("/logs")
def usage_logs(user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    query = select(UsageLog).order_by(UsageLog.created_at.desc()).limit(200)
    if user.role != "super_admin": query = query.where(UsageLog.user_id == user.id)
    items = db.scalars(query).all()
    return [{"id": item.id, "requestId": item.request_id, "model": item.model_id, "status": item.status, "inputTokens": item.input_tokens, "outputTokens": item.output_tokens, "cost": item.cost, "latencyMs": item.latency_ms, "createdAt": item.created_at.strftime("%d/%m/%Y %H:%M:%S")} for item in items]

