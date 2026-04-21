# BuyruqSportedu — Backend

Django 5 + DRF asosidagi topshiriqlar boshqaruv tizimi.

## 1. Redis o'rnatish (Windows)

Memurai (Redis for Windows) o'rnating:
https://www.memurai.com/get-memurai

Yoki WSL2 orqali:
```bash
wsl --install
wsl -d Ubuntu
sudo apt update && sudo apt install redis-server
sudo service redis-server start
```

## 2. PostgreSQL yaratish

```sql
CREATE DATABASE buyruqsportedu;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE buyruqsportedu TO postgres;
```

## 3. Virtual environment va kutubxonalar

```bash
cd D:/Python/Projects/JiraSportedu
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements/local.txt
```

## 4. .env sozlash

```bash
copy .env.example .env
# .env faylini oching va o'z ma'lumotlaringizni kiriting
```

## 5. Migrations va superuser

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

## 6. Ishga tushirish

**Terminal 1 — Django server:**
```bash
venv\Scripts\activate
python manage.py runserver
```

**Terminal 2 — Celery worker:**
```bash
venv\Scripts\activate
celery -A config worker -l info -P gevent
```

**Terminal 3 — Celery beat (scheduled tasks):**
```bash
venv\Scripts\activate
celery -A config beat -l info
```

## API docs

- Admin panel: http://localhost:8000/admin/
- API base: http://localhost:8000/api/

## Asosiy endpointlar

| Method | URL | Tavsif |
|--------|-----|--------|
| POST | /api/auth/register/ | Ro'yxatdan o'tish |
| POST | /api/auth/login/ | Kirish (JWT token) |
| POST | /api/auth/token/refresh/ | Token yangilash |
| GET | /api/auth/me/ | Joriy foydalanuvchi |
| GET/POST | /api/tasks/ | Topshiriqlar ro'yxati |
| PATCH | /api/tasks/{id}/status/ | Status o'zgartirish |
| GET | /api/reports/overview/ | Umumiy hisobot |
| GET | /api/admin/users/ | Foydalanuvchilar (SuperAdmin) |
