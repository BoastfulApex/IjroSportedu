#!/usr/bin/env python3
"""
VAPID kalitlarini generatsiya qilish.
Ishlatish:
  cd /home/ubuntu/IjroSportedu/IjroSportedu
  source venv/bin/activate
  python ../deploy/generate_vapid.py
"""
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import base64

private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

# Private key — raw 32 bytes, base64url (pywebpush Vapid.from_string() uchun)
private_numbers = private_key.private_numbers()
private_raw = private_numbers.private_value.to_bytes(32, "big")
private_b64 = base64.urlsafe_b64encode(private_raw).decode().rstrip("=")

# Public key — uncompressed point, base64url (browser uchun)
public_bytes = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
public_b64 = base64.urlsafe_b64encode(public_bytes).decode().rstrip("=")

print("=" * 60)
print(".env fayliga quyidagilarni qo'shing:")
print("=" * 60)
print(f"VAPID_PUBLIC_KEY={public_b64}")
print(f"VAPID_PRIVATE_KEY={private_b64}")
print(f"VAPID_ADMIN_EMAIL=admin@sportedu.uz")
print("=" * 60)
print()
print("Frontend uchun .env.production fayliga:")
print(f"VITE_VAPID_PUBLIC_KEY={public_b64}")
