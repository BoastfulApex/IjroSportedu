#!/bin/bash
# BuyruqSportedu — Ubuntu 22.04 server sozlash skripti
# Ishlatish: sudo bash setup_server.sh

set -e

echo "=== 1. Tizim paketlarini yangilash ==="
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx redis-server git curl

echo "=== 2. Node.js 20 o'rnatish ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

echo "=== 3. PostgreSQL sozlash ==="
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
mkdir -p /var/log/buyruqsportedu
mkdir -p /var/run/buyruqsportedu
chown -R www-data:www-data /var/www/buyruqsportedu
chown -R www-data:www-data /var/log/buyruqsportedu
chown -R www-data:www-data /var/run/buyruqsportedu

echo "=== 5. Redis va PostgreSQL ishga tushirish ==="
systemctl enable redis-server postgresql
systemctl start redis-server postgresql

echo "=== Tayyor! Endi deploy.sh ni ishga tushiring ==="
