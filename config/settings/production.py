from .base import *  # noqa

DEBUG = False

# Production'da Django admin standart holatda O'CHIRILGAN (pentest Y1).
# Yoqish uchun .env: ADMIN_URL=<maxfiy-manzil>/  (masalan boshqaruv-x7k2/)
ADMIN_URL = env("ADMIN_URL", default="")  # noqa: F405

# Production'da faqat JSON — DRF Browsable API (?format=api) o'chirilgan (pentest Y4)
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ── HTTPS (pentest Y5/O1) ─────────────────────────────────────────────
# SSL tashqi nginx'da tugaydi; u "X-Forwarded-Proto: https" yuboradi,
# django-2 nginx uni o'zgartirmasdan uzatadi ($http_x_forwarded_proto).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000            # 1 yil
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Fayllarni nginx beradi (X-Accel-Redirect → location /protected-media/ { internal; })
USE_X_ACCEL_REDIRECT = env.bool("USE_X_ACCEL_REDIRECT", default=True)  # noqa: F405

CSRF_TRUSTED_ORIGINS = [
    "https://ijro.sportedu.uz",
    "https://www.ijro.sportedu.uz",
    "https://api-ijro.sportedu.uz",
]
