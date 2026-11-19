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

CSRF_TRUSTED_ORIGINS = [
    "https://ijro.sportedu.uz",
    "https://www.ijro.sportedu.uz",
    "https://api-ijro.sportedu.uz",
]
