#!/bin/bash
# BuyruqSportedu — Ubuntu server birinchi marta sozlash
# Ishlatish: sudo bash setup_server.sh

set -e

echo "=== 1. Tizim yangilash ==="
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib nginx redis-server git curl

echo "=== 2. Node.js 20 o'rnatish ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

echo "=== 3. PostgreSQL — database va user yaratish ==="
sudo -u postgres psql <<EOF
CREATE DATABASE buyruqsportedu;
CREATE USER buyruquser WITH PASSWORD 'kuchli_parol_bu_yerda';
ALTER ROLE buyruquser SET client_encoding TO 'utf8';
ALTER ROLE buyruquser SET default_transaction_isolation TO 'read committed';
ALTER ROLE buyruquser SET timezone TO 'Asia/Tashkent';
GRANT ALL PRIVILEGES ON DATABASE buyruqsportedu TO buyruquser;
\c buyruqsportedu
GRANT ALL ON SCHEMA public TO buyruquser;
EOF

echo "=== 4. Papkalar yaratish ==="
mkdir -p /var/www/buyruqsportedu/backend
mkdir -p /var/www/buyruqsportedu/frontend

echo "=== 5. Redis va PostgreSQL autostart ==="
systemctl enable redis-server postgresql
systemctl start redis-server postgresql

echo ""
echo "============================================"
echo " Server sozlandi!"
echo " Endi kod fayllarini yuklang:"
echo " /var/www/buyruqsportedu/backend/  — Django"
echo " /var/www/buyruqsportedu/frontend/ — React"
echo " Keyin: sudo bash deploy.sh"
echo "============================================"
