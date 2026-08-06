from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import ApiKey, ModelCatalog, Transaction, UsageLog, User, UserModel, UserSetting
from app.core.security import hash_api_secret, hash_password
from app.modules.models.catalog import MODELS


def seed_database(db: Session) -> None:
    if db.scalar(select(User).where(User.email == "admin@nexora.vn")):
        return
    for model in MODELS:
        db.add(ModelCatalog(id=model["id"], provider=model["provider"], display_name=model["displayName"], input_price=model["inputPrice"], output_price=model["outputPrice"], enabled=model["enabled"]))
    admin = User(name="Nexora Admin", email="admin@nexora.vn", password_hash=hash_password("admin123"), role="super_admin", balance=12_450_000, token_quota=999_999_999, token_used=12_600_000)
    user = User(name="Nguyen Thuan", email="user@nexora.vn", password_hash=hash_password("user123"), balance=490_000, token_quota=5_000_000, token_used=1_452_682)
    demo = User(name="Tran Minh Anh", email="minhanh@nexora.vn", password_hash=hash_password("demo123"), balance=1_250_000, token_quota=12_000_000, token_used=3_420_100)
    locked = User(name="Le Hoang Nam", email="hoangnam@nexora.vn", password_hash=hash_password("demo123"), status="locked", balance=0, token_quota=1_000_000, token_used=1_000_000)
    db.add_all([admin, user, demo, locked]); db.flush()
    db.add_all([UserModel(user_id=user.id, model_id="gpt-5.5"), UserModel(user_id=user.id, model_id="claude-opus-4.8"), UserModel(user_id=demo.id, model_id="deepseek-v4-flash")])
    db.add_all([Transaction(user_id=user.id, type="credit", amount=500_000, description="Chuyen khoan QR - NX8472"), Transaction(user_id=user.id, type="debit", amount=84_500, description="Usage gpt-5.5 / API production"), Transaction(user_id=user.id, type="credit", amount=300_000, description="Admin credit")])
    db.add(ApiKey(user_id=user.id, name="Production", prefix="nx-live-a82K", secret_hash=hash_api_secret("demo-secret")))
    for index, model_id in enumerate(["gpt-5.5", "claude-opus-4.8", "gpt-5.5", "claude-opus-4.8"]):
        db.add(UsageLog(user_id=user.id, model_id=model_id, status="success" if index != 2 else "failed", input_tokens=1250 + index * 430, output_tokens=320 + index * 70, cost=1800 + index * 600, latency_ms=840 + index * 125, request_id=f"req_demo_{index + 1}"))
    for item in [admin, user, demo, locked]: db.add(UserSetting(user_id=item.id))
    db.commit()
