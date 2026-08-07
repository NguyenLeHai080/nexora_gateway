from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import ModelCatalog, UserModel

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("")
def list_models(user=Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    models = db.scalars(select(ModelCatalog).join(UserModel).where(UserModel.user_id == user.id, ModelCatalog.enabled.is_(True))).all()
    return [{"id": item.id, "provider": item.provider, "displayName": item.display_name, "inputPrice": item.input_price, "outputPrice": item.output_price, "enabled": item.enabled} for item in models]
