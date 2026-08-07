import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.models import ApiKey
from app.core.security import hash_api_secret

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class CreateKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    quota: int | None = Field(default=None, ge=1)


class UpdateKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    quota: int | None = Field(default=None, ge=1)


class ValidateKeyRequest(BaseModel):
    key_id: int
    secret: str = Field(min_length=10, max_length=255)


def serialize(item: ApiKey, secret: str | None = None) -> dict:
    data = {"id": item.id, "name": item.name, "prefix": item.prefix, "status": item.status, "quota": item.quota, "createdAt": item.created_at.strftime("%d/%m/%Y"), "lastUsed": item.last_used.strftime("%d/%m/%Y %H:%M") if item.last_used else None}
    if secret: data["key"] = secret
    return data


@router.get("")
def list_keys(user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [serialize(item) for item in db.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc()))]


@router.post("")
def create_key(payload: CreateKeyRequest, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    raw = f"nx-{secrets.token_urlsafe(28)}"
    item = ApiKey(user_id=user.id, name=payload.name, prefix=raw[:14], secret_hash=hash_api_secret(raw), quota=payload.quota)
    db.add(item); db.commit(); db.refresh(item)
    return serialize(item, raw)


@router.post("/validate")
def validate_key(payload: ValidateKeyRequest, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(ApiKey).where(ApiKey.id == payload.key_id, ApiKey.user_id == user.id, ApiKey.status == "active"))
    if not item or item.secret_hash != hash_api_secret(payload.secret.strip()):
        raise HTTPException(400, "API key secret does not match the selected active key")
    return {"valid": True, "prefix": item.prefix}


@router.patch("/{key_id}/toggle")
def toggle_key(key_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if not item: raise HTTPException(404, "API key not found")
    item.status = "disabled" if item.status == "active" else "active"; db.commit()
    return serialize(item)


@router.put("/{key_id}")
def update_key(key_id: int, payload: UpdateKeyRequest, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    item = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if not item: raise HTTPException(404, "API key not found")
    item.name = payload.name.strip(); item.quota = payload.quota; db.commit()
    return serialize(item)


@router.delete("/{key_id}", status_code=204)
def delete_key(key_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    item = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if not item: raise HTTPException(404, "API key not found")
    db.delete(item); db.commit()
    return Response(status_code=204)
