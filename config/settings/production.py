from .base import *  # noqa

DEBUG = False

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = [
    "https://ijro.sportedu.uz",
    "https://www.ijro.sportedu.uz",
    "https://api-ijro.sportedu.uz",
]
