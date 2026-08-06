from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.models import Transaction

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/transactions")
def list_transactions(user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc())).all()
    return [{"id": item.id, "createdAt": item.created_at.strftime("%d/%m/%Y %H:%M"), "type": item.type, "amount": item.amount, "description": item.description} for item in items]

