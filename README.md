# Nexora Gateway Console

Monorepo quan ly tai khoan, token va model cua 9Router.

## Chay toan bo he thong

Nexora la control plane; 9Router la routing engine noi bo. Hai service khong ghi
chung mot file SQLite, nhung duoc quan ly tap trung qua API cua Nexora.

```powershell
Copy-Item .env.example .env
# Sua cac secret va dung cung mot mat khau cho
# NINE_ROUTER_DASHBOARD_PASSWORD va INITIAL_PASSWORD.
docker compose up --build
```

Mo `http://localhost:8080`. Dashboard 9Router chi bind localhost tai
`http://localhost:20128`; provider, model va trang thai duoc quan ly tai menu
`9Router & Models` cua Nexora.

## Chay nhanh

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Mo `http://localhost:5173`.

Tai khoan demo:

- Super Admin: `admin@nexora.vn` / `admin123`
- Nguoi dung: `user@nexora.vn` / `user123`

Swagger API: `http://localhost:8000/docs`.

## Ket noi OpenAI-compatible

Sau khi tao API key va duoc cap model, client dung:

- Base URL: `http://localhost:8000/v1`
- Endpoint: `/chat/completions`, `/models`
- Header: `Authorization: Bearer <NEXORA_API_KEY>`

De chay rieng tung service khi phat trien, copy `backend/.env.example` thanh
`backend/.env` va cau hinh `NINE_ROUTER_BASE_URL`, `NINE_ROUTER_API_KEY`,
`NINE_ROUTER_DASHBOARD_PASSWORD`.
