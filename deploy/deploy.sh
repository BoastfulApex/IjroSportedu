#!/bin/bash
# BuyruqSportedu — ijro.sportedu.uz deploy skripti
# Ishlatish: sudo bash deploy.sh

set -e

BACKEND_DIR="/var/www/buyruqsportedu/backend"
FRONTEND_DIR="/var/www/buyruqsportedu/frontend"

echo "=== 1. Backend — virtual muhit ==="
cd $BACKEND_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/production.txt
pip install google-auth

echo "=== 2. .env sozlash ==="
# .env allaqachon serverga ko'chirilgan bo'lishi kerak (scp orqali)
if [ ! -f ".env" ]; then
  echo "XATO: .env fayli topilmadi! Ko'chirish: scp .env user@server:/var/www/buyruqsportedu/backend/.env"
  exit 1
fi

echo "=== 3. Migrate va static fayllar ==="
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "=== 4. Log va run papkalar ==="
mkdir -p /var/log/buyruqsportedu
mkdir -p /var/run/buyruqsportedu
chown -R www-data:www-data /var/log/buyruqsportedu
chown -R www-data:www-data /var/run/buyruqsportedu
chown -R www-data:www-data $BACKEND_DIR

echo "=== 5. Frontend — tayyor dist fayllarini tekshirish ==="
if [ ! -f "$FRONTEND_DIR/index.html" ]; then
  echo "XATO: $FRONTEND_DIR/index.html topilmadi!"
  echo "Ko'chirish: scp -r dist/* user@server:/var/www/buyruqsportedu/frontend/"
  exit 1
fi
chown -R www-data:www-data $FRONTEND_DIR
echo "Frontend tayyor: $FRONTEND_DIR"

echo "=== 6. Systemd service ==="
cp $BACKEND_DIR/deploy/buyruqsportedu.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable buyruqsportedu
systemctl restart buyruqsportedu
systemctl status buyruqsportedu --no-pager

echo "=== 7. Nginx ==="
cp $BACKEND_DIR/deploy/nginx.conf /etc/nginx/sites-available/buyruqsportedu
ln -sf /etc/nginx/sites-available/buyruqsportedu /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "============================================"
echo " Deploy muvaffaqiyatli tugadi!"
echo " http://ijro.sportedu.uz"
echo " http://192.168.10.242"
echo "============================================"
