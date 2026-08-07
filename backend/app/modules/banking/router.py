import math
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_super_admin
from app.core.models import AuditLog, BankAccount, BankQrImage, BankWebhookEvent, DepositOrder, ModelCatalog, TokenXFundingAllocation, Transaction, User, UserModel

router = APIRouter(tags=["Banking"])

class BankRequest(BaseModel):
    bank_code: str = Field(min_length=2, max_length=30)
    bank_name: str = Field(min_length=2, max_length=100)
    account_number: str = Field(min_length=4, max_length=50)
    account_name: str = Field(min_length=2, max_length=120)
    enabled: bool = True

class DepositRequest(BaseModel):
    bank_account_id: int
    amount: int = Field(ge=1000, le=500_000_000)

class QrImageRequest(BaseModel):
    image_data: str = Field(min_length=100, max_length=3_000_000)

def bank_json(item: BankAccount, db: Session | None = None) -> dict:
    has_custom_qr = bool(db and db.get(BankQrImage, item.id))
    return {"id":item.id,"bankCode":item.bank_code,"bankName":item.bank_name,"accountNumber":item.account_number,"accountName":item.account_name,"enabled":item.enabled,"qrImageUrl":f"/api/banking/qr/{item.id}" if has_custom_qr else None}

def automatic_token_quota(db:Session,user_id:int,amount:int) -> int:
    prices=db.execute(select(ModelCatalog.input_price,ModelCatalog.output_price).join(UserModel,UserModel.model_id==ModelCatalog.id).where(UserModel.user_id==user_id,ModelCatalog.enabled.is_(True))).all()
    positive=[max(input_price,output_price) for input_price,output_price in prices if input_price>0 and output_price>0]
    reference=max(positive) if positive else 3500
    return math.floor(amount*1_000_000/reference)

def normalized_transfer_content(value:str) -> str:
    """Bank descriptions may insert spaces/punctuation into the requested code."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())

def tokenx_transfer_code(user: User) -> str:
    username = re.sub(r"[^a-zA-Z0-9]", "", user.name).lower() or "user"
    username = f"{username}{user.id}"
    return f"tkx{username}"

def deposit_match_code(order:DepositOrder, db:Session) -> str:
    return normalized_transfer_content(tokenx_transfer_code(db.get(User, order.user_id)))

def order_json(item: DepositOrder, bank: BankAccount, user: User) -> dict:
    transfer_code=tokenx_transfer_code(user)
    qr = f"https://img.vietqr.io/image/{quote(bank.bank_code)}-{quote(bank.account_number)}-compact2.png?amount={item.expected_amount}&addInfo={quote(transfer_code)}&accountName={quote(bank.account_name)}"
    return {"id":item.id,"code":transfer_code,"expectedAmount":item.expected_amount,"paidAmount":item.paid_amount,"tokenAmount":item.token_amount,"status":item.status,"expiresAt":item.expires_at.isoformat(),"createdAt":item.created_at.isoformat(),"qrUrl":qr,"bank":bank_json(bank)}

@router.get("/admin/bank-accounts")
def admin_banks(_:User=Depends(require_super_admin),db:Session=Depends(get_db)) -> list[dict]:
    return [bank_json(x,db) for x in db.scalars(select(BankAccount).order_by(BankAccount.id.desc()))]

@router.post("/admin/bank-accounts",status_code=201)
def create_bank(payload:BankRequest,admin:User=Depends(require_super_admin),db:Session=Depends(get_db)) -> dict:
    item=BankAccount(**payload.model_dump(),token_price_per_million=2100,minimum_amount=1000);db.add(item);db.flush();db.add(AuditLog(actor_id=admin.id,action="bank.created",target=f"bank:{item.id}",details=item.account_number));db.commit();db.refresh(item);return bank_json(item,db)

@router.put("/admin/bank-accounts/{bank_id}")
def update_bank(bank_id:int,payload:BankRequest,admin:User=Depends(require_super_admin),db:Session=Depends(get_db)) -> dict:
    item=db.get(BankAccount,bank_id)
    if not item: raise HTTPException(404,"Bank account not found")
    for key,value in payload.model_dump().items():setattr(item,key,value)
    db.add(AuditLog(actor_id=admin.id,action="bank.updated",target=f"bank:{item.id}",details=item.account_number));db.commit();db.refresh(item);return bank_json(item,db)

@router.delete("/admin/bank-accounts/{bank_id}",status_code=204)
def delete_bank(bank_id:int,admin:User=Depends(require_super_admin),db:Session=Depends(get_db)) -> Response:
    item=db.get(BankAccount,bank_id)
    if not item: raise HTTPException(404,"Bank account not found")
    item.enabled=False;db.add(AuditLog(actor_id=admin.id,action="bank.disabled",target=f"bank:{item.id}",details=item.account_number));db.commit();return Response(status_code=204)

@router.get("/wallet/bank-accounts")
def public_banks(_:User=Depends(get_current_user),db:Session=Depends(get_db)) -> list[dict]:
    return [bank_json(x,db) for x in db.scalars(select(BankAccount).where(BankAccount.enabled.is_(True)))]

@router.put("/admin/bank-accounts/{bank_id}/qr")
def upload_bank_qr(bank_id:int,payload:QrImageRequest,admin:User=Depends(require_super_admin),db:Session=Depends(get_db)) -> dict:
    bank=db.get(BankAccount,bank_id)
    if not bank:raise HTTPException(404,"Bank account not found")
    if not payload.image_data.startswith("data:image/png;base64,"):raise HTTPException(400,"Cropped QR must be a PNG data URL")
    item=db.get(BankQrImage,bank_id)
    if item:item.image_data=payload.image_data
    else:db.add(BankQrImage(bank_account_id=bank_id,image_data=payload.image_data))
    db.add(AuditLog(actor_id=admin.id,action="bank.qr_uploaded",target=f"bank:{bank_id}",details="Auto-cropped QR image"));db.commit()
    return bank_json(bank,db)

@router.get("/banking/qr/{bank_id}")
def bank_qr_image(bank_id:int,db:Session=Depends(get_db)) -> Response:
    item=db.get(BankQrImage,bank_id)
    if not item:raise HTTPException(404,"Custom QR not found")
    import base64
    try:data=base64.b64decode(item.image_data.split(",",1)[1],validate=True)
    except Exception as exc:raise HTTPException(500,"Stored QR is invalid") from exc
    return Response(content=data,media_type="image/png",headers={"Cache-Control":"public, max-age=300"})

@router.get("/wallet/deposits")
def deposits(user:User=Depends(get_current_user),db:Session=Depends(get_db)) -> list[dict]:
    rows=db.scalars(select(DepositOrder).where(DepositOrder.user_id==user.id).order_by(DepositOrder.id.desc())).all();return [order_json(x,db.get(BankAccount,x.bank_account_id),user) for x in rows]

@router.post("/wallet/deposits",status_code=201)
def create_deposit(payload:DepositRequest,user:User=Depends(get_current_user),db:Session=Depends(get_db)) -> dict:
    bank=db.get(BankAccount,payload.bank_account_id)
    if not bank or not bank.enabled:raise HTTPException(404,"Bank account unavailable")
    code=f"NX{user.id}{secrets.token_hex(3).upper()}"
    item=DepositOrder(user_id=user.id,bank_account_id=bank.id,code=code,expected_amount=payload.amount,token_amount=0,expires_at=datetime.utcnow()+timedelta(minutes=30));db.add(item);db.commit();db.refresh(item);return order_json(item,bank,user)

@router.post("/webhook/sepay")
@router.post("/banking/webhooks/sepay")
def sepay_webhook(payload:dict,authorization:str=Header(default=""),db:Session=Depends(get_db)) -> dict:
    if not secrets.compare_digest(authorization,f"Apikey {settings.banking_webhook_api_key}"):raise HTTPException(401,"Invalid webhook credential")
    external_id=str(payload.get("id") or payload.get("referenceCode") or "").strip();amount=int(payload.get("transferAmount") or 0);content=normalized_transfer_content(str(payload.get("content") or payload.get("description") or ""));account=re.sub(r"\D","",str(payload.get("accountNumber") or ""));transfer_type=str(payload.get("transferType") or "").lower()
    if not external_id:raise HTTPException(400,"Missing transaction id")
    if db.scalar(select(BankWebhookEvent).where(BankWebhookEvent.external_id==external_id)):return {"success":True,"duplicate":True}
    event=BankWebhookEvent(external_id=external_id,payload_json=payload,status="ignored");db.add(event)
    if transfer_type not in {"in","credit"} or amount<=0:db.commit();return {"success":True,"matched":False}
    reconciliation_since=datetime.utcnow()-timedelta(days=7)
    candidates=db.scalars(select(DepositOrder).where(DepositOrder.status=="pending",DepositOrder.created_at>=reconciliation_since).order_by(DepositOrder.id.desc())).all()
    order=next((x for x in candidates if deposit_match_code(x,db) in content),None)
    if not order:db.commit();return {"success":True,"matched":False}
    bank=db.get(BankAccount,order.bank_account_id)
    if account and re.sub(r"\D","",bank.account_number)!=account:db.commit();return {"success":True,"matched":False}
    user=db.get(User,order.user_id);user.balance+=amount;order.status="paid";order.paid_amount=amount;order.token_amount=0;order.external_transaction_id=external_id;order.paid_at=datetime.utcnow();event.status="credited";db.add(Transaction(user_id=user.id,type="credit",amount=amount,description=f"Bank deposit {order.code}"))
    reserve_percent=max(0,min(100,settings.tokenx_deposit_reserve_percent));reserve_amount=amount*reserve_percent//100
    db.add(TokenXFundingAllocation(deposit_order_id=order.id,user_id=user.id,gross_amount=amount,reserve_amount=reserve_amount,owner_amount=amount-reserve_amount,reserve_percent=reserve_percent,status="reserved"))
    try:db.commit()
    except IntegrityError:db.rollback();return {"success":True,"duplicate":True}
    return {"success":True,"matched":True,"credited":True,"amount":amount,"tokens":0,"tokenxReserve":reserve_amount,"ownerAmount":amount-reserve_amount}
