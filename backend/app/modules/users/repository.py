from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import User


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "balance": user.balance,
        "tokenQuota": user.token_quota,
        "tokenUsed": user.token_used,
        "models": [item.model_id for item in user.model_entitlements],
        "createdAt": user.created_at.strftime("%d/%m/%Y"),
    }


class UsersRepository:
    def get(self, db: Session, user_id: int) -> User | None:
        return db.get(User, user_id)

    def find_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email.lower()))

    def list_clients(self, db: Session) -> list[User]:
        return list(db.scalars(select(User).where(User.role == "user").order_by(User.created_at.desc())))


users_repository = UsersRepository()
