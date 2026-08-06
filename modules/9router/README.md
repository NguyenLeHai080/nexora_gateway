# 9Router module

Source 9Router duoc vendor tai `modules/9router/app`. Module chiu trach nhiem provider routing, OAuth/provider accounts va usage analytics. Auth khach hang, API key `nx-*`, vi, quota va model entitlement van do Nexora kiem soat.

## Tai su dung du lieu hien tai

Compose dung external volume `9router-data`, trung voi container 9Router dang chay. Khong chay hai container cung ghi vao volume nay.

1. Dung stack 9Router cu.
2. Copy `.env.example` thanh `.env` va dien cac secret hien tai.
3. Chay:

```powershell
docker compose -f modules/9router/docker-compose.yml up -d
```

Trong Docker network, backend Nexora su dung `http://router:20128/v1`. Khi backend chay tren Windows host, tiep tuc su dung `http://9route.test/v1` hoac `http://localhost:20128/v1`.
