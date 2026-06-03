#!/bin/bash
# BuyruqSportedu — Yangi server sozlash skripti
# Yo'l: /home/user/IjroSportedu/
# Ishlatish: sudo bash /home/user/IjroSportedu/IjroSportedu/deploy/server_setup.sh

set -e

BACKEND_DIR="/home/user/IjroSportedu/IjroSportedu"
FRONTEND_DIR="/home/user/IjroSportedu/FrontEnd"
APP_USER="user"

echo "================================================"
echo " BuyruqSportedu — Server sozlash"
echo " Backend:  $BACKEND_DIR"
echo " Frontend: $FRONTEND_DIR"
echo "================================================"
echo ""

# ── 1. Paketlar ──────────────────────────────────────────────────
echo "=== 1. Tizim paketlari o'rnatilmoqda ==="
apt update && apt upgrade -y
apt install -y \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    git curl

# ── 2. PostgreSQL ─────────────────────────────────────────────────
echo ""
echo "=== 2. PostgreSQL: baza va foydalanuvchi yaratish ==="
sudo -u postgres psql <<EOF
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'buyruquser') THEN
    CREATE USER buyruquser WITH PASSWORD 'kuchli_parol';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE buyruqsportedu OWNER buyruquser'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'buyruqsportedu')\gexec

ALTER ROLE buyruquser SET client_encoding TO 'utf8';
ALTER ROLE buyruquser SET default_transaction_isolation TO 'read committed';
ALTER ROLE buyruquser SET timezone TO 'Asia/Tashkent';
GRANT ALL PRIVILEGES ON DATABASE buyruqsportedu TO buyruquser;
\c buyruqsportedu
GRANT ALL ON SCHEMA public TO buyruquser;
EOF
echo "✅ PostgreSQL tayyor"

# ── 3. Redis & PostgreSQL autostart ──────────────────────────────
echo ""
echo "=== 3. Redis va PostgreSQL autostart ==="
systemctl enable redis-server postgresql
systemctl start redis-server postgresql
echo "✅ Redis va PostgreSQL ishga tushdi"

# ── 4. Log va PID papkalar ────────────────────────────────────────
echo ""
echo "=== 4. Log papkalar yaratish ==="
mkdir -p /var/log/buyruqsportedu
mkdir -p /var/run/buyruqsportedu
chown -R $APP_USER:$APP_USER /var/log/buyruqsportedu
chown -R $APP_USER:$APP_USER /var/run/buyruqsportedu
echo "✅ Log papkalar tayyor"

# ── 5. Python venv ────────────────────────────────────────────────
echo ""
echo "=== 5. Python virtual muhit va kutubxonalar ==="
cd $BACKEND_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/production.txt
echo "✅ Python kutubxonalar o'rnatildi"

# ── 6. .env tekshirish ────────────────────────────────────────────
echo ""
echo "=== 6. .env fayli tekshirilmoqda ==="
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "⚠️  .env fayli topilmadi!"
    echo "   .env.production ni nusxalash:"
    cp $BACKEND_DIR/.env.production $BACKEND_DIR/.env
    echo "✅ .env yaratildi (.env.production dan)"
else
    echo "✅ .env mavjud"
fi

# ── 7. Django migrate va collectstatic ───────────────────────────
echo ""
echo "=== 7. Django migrate va static fayllar ==="
source $BACKEND_DIR/venv/bin/activate
cd $BACKEND_DIR
python manage.py migrate --noinput
python manage.py collectstatic --noinput
echo "✅ Migrate va collectstatic bajarildi"

# ── 8. Systemd services ───────────────────────────────────────────
echo ""
echo "=== 8. Systemd servislar ==="
cp $BACKEND_DIR/deploy/buyruqsportedu.service /etc/systemd/system/ijrosportedu.service
cp $BACKEND_DIR/deploy/celery.service         /etc/systemd/system/ijrosportedu-celery.service
systemctl daemon-reload
systemctl enable ijrosportedu ijrosportedu-celery
systemctl start  ijrosportedu ijrosportedu-celery
echo "✅ Django va Celery servislar ishga tushdi"

# ── 9. Nginx ─────────────────────────────────────────────────────
echo ""
echo "=== 9. Nginx sozlanmoqda ==="
cp $BACKEND_DIR/deploy/nginx.conf /etc/nginx/sites-available/ijrosportedu
ln -sf /etc/nginx/sites-available/ijrosportedu /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
systemctl enable nginx
echo "✅ Nginx sozlandi"

# ── 10. Ruxsatlar ────────────────────────────────────────────────
echo ""
echo "=== 10. Fayl ruxsatlari ==="
chown -R $APP_USER:$APP_USER $BACKEND_DIR
chown -R $APP_USER:$APP_USER $FRONTEND_DIR
# Nginx media va static o'qiy olsin
chmod -R 755 $FRONTEND_DIR
chmod -R 755 $BACKEND_DIR/staticfiles
chmod -R 755 $BACKEND_DIR/media
echo "✅ Ruxsatlar sozlandi"

# ── Natija ───────────────────────────────────────────────────────
echo ""
echo "============================================"
echo " ✅ Server muvaffaqiyatli sozlandi!"
echo ""
echo " Tekshirish:"
echo "   systemctl status ijrosportedu"
echo "   systemctl status ijrosportedu-celery"
echo "   curl http://localhost:8002/api/auth/me/"
echo ""
echo " Sayt: http://ijro.sportedu.uz"
echo "============================================"
