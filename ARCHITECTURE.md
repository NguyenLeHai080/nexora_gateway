# Kien truc Nexora Gateway

## Frontend

Moi menu la mot module doc lap trong `frontend/src/modules`:

- `auth`: store phien dang nhap, hook va route guard.
- `dashboard`, `wallet`, `api-keys`, `models`: khu vuc nguoi dung.
- `admin`: tai khoan, dong tien va 9Router danh cho Super Admin.
- `core`: API client, layout, navigation, types va cau hinh dung chung.
- `shared`: component va utility khong gan voi nghiep vu.

Module khong truy cap truc tiep du lieu cua module khac. Quyen menu va route deu bam vao `core auth`.

## Backend

Backend FastAPI chia theo cung domain trong `backend/app/modules`. `core` chua config, SQLAlchemy, JWT, password hashing va dependency RBAC. Router chi xu ly HTTP; repository va service la noi dat quy tac nghiep vu.

Ban hien tai luu ben vung bang SQLAlchemy va SQLite; chi can doi `DATABASE_URL` de chuyen sang PostgreSQL. Gateway `/v1` tuong thich OpenAI va forward request sang 9Router sau khi kiem tra key, account, model entitlement, quota va so du.

## Quyen so huu du lieu

- Nexora la nguon chinh cho user, RBAC, vi, quota, client API key, model catalog va audit.
- 9Router la nguon chinh cho provider credential, connection, proxy, routing va upstream usage.
- FastAPI la ranh gioi quan ly duy nhat cua frontend. Frontend khong doc DB hay goi truc tiep API quan tri 9Router.
- Model duoc pull tu 9Router vao `model_catalog`; provider credential chi duoc chuyen tiep va khong luu tai Nexora.

## Luong cap quyen

1. Super Admin tao tai khoan va nap tien.
2. Ledger ghi giao dich credit, service quy doi quota theo chinh sach.
3. Super Admin cap model tu catalog 9Router cho account.
4. Client tao API key va goi gateway OpenAI-compatible.
5. Gateway kiem tra account, key, model entitlement va so du truoc khi chuyen request.
6. Usage service ghi input/output token, chi phi upstream va debit tai khoan.
