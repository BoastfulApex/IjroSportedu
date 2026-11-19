from .base import *  # noqa

DEBUG = False

# Production'da Django admin standart holatda O'CHIRILGAN (pentest Y1).
# Yoqish uchun .env: ADMIN_URL=<maxfiy-manzil>/  (masalan boshqaruv-x7k2/)
ADMIN_URL = env("ADMIN_URL", default="")  # noqa: F405

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = [
    "https://ijro.sportedu.uz",
    "https://www.ijro.sportedu.uz",
    "https://api-ijro.sportedu.uz",
]
