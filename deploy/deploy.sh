#!/bin/bash
# BuyruqSportedu — Deploy skripti
# Har safar yangi versiya chiqarganda ishlatiladi
# Ishlatish: sudo bash deploy.sh

set -e

BACKEND_DIR="/var/www/buyruqsportedu/backend"
FRONTEND_DIR="/var/www/buyruqsportedu/frontend"

echo "=== 1. Kod yuklash ==="
# Agar git bilan ishlasangiz:
# cd $BACKEND_DIR && git pull origin main

echo "=== 2. Backend — virtual muhit va kutubxonalar ==="
cd $BACKEND_DIR
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements/production.txt

echo "=== 3. Backend — .env fayl nusxalash ==="
# .env.production faylini .env ga ko'chiring
cp .env.production .env

echo "=== 4. Backend — migrate va static fayllar ==="
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo "=== 5. Frontend — build ==="
cd $FRONTEND_DIR
npm ci
npm run build

echo "=== 6. Systemd service sozlash ==="
cp $BACKEND_DIR/deploy/buyruqsportedu.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable buyruqsportedu
systemctl restart buyruqsportedu

echo "=== 7. Nginx sozlash ==="
# SERVER_IP ni haqiqiy IP bilan almashtiring
sed -i "s/SERVER_IP/$(hostname -I | awk '{print $1}')/g" $BACKEND_DIR/deploy/nginx.conf
cp $BACKEND_DIR/deploy/nginx.conf /etc/nginx/sites-available/buyruqsportedu
ln -sf /etc/nginx/sites-available/buyruqsportedu /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "=== Deploy muvaffaqiyatli tugadi! ==="
echo "Backend: http://$(hostname -I | awk '{print $1}')/api/"
echo "Frontend: http://$(hostname -I | awk '{print $1}')/"
