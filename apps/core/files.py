"""Himoyalangan fayllar: imzolangan havolalar va nginx X-Accel-Redirect orqali berish.

/media/ nginx'da yopiq. Fayl faqat ikki yo'l bilan beriladi:
1. Imzolangan havola (`signed_file_url`) — serializer faqat foydalanuvchi ko'ra oladigan
   obyektlar uchun chiqaradi; imzoni soxtalashtirib bo'lmaydi, muddati cheklangan.
2. Ruxsat tekshiradigan download endpointlari (`file_response`).
"""
import mimetypes
import os
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.http import FileResponse, HttpResponse
from django.urls import reverse

SALT = "apps.core.protected-file"
# Inline ko'rsatiladigan turlar; qolganlari (shu jumladan HTML, SVG) — faqat yuklab olish
_INLINE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "application/pdf"}


def signed_file_url(request, fieldfile, filename=None):
    """Fayl uchun imzolangan, muddatli havola (yoki fayl bo'lmasa None)."""
    if not fieldfile:
        return None
    token = signing.dumps({"p": fieldfile.name, "n": filename or ""}, salt=SALT, compress=True)
    path = reverse("protected-file", args=[token])
    return request.build_absolute_uri(path) if request else path


def load_signed_token(token):
    """(fayl yo'li, fayl nomi) yoki imzo noto'g'ri/muddati o'tgan bo'lsa signing.BadSignature."""
    data = signing.loads(token, salt=SALT, max_age=settings.PROTECTED_MEDIA_MAX_AGE)
    return data["p"], data.get("n") or os.path.basename(data["p"])


def _content_disposition(filename, inline):
    ascii_name = filename.encode("ascii", "ignore").decode() or "file"
    ascii_name = ascii_name.replace('"', "").replace("\\", "")
    kind = "inline" if inline else "attachment"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def file_response(storage_name, filename):
    """Faylni beradi: production'da nginx X-Accel-Redirect, lokalda Django FileResponse."""
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"
    inline = content_type in _INLINE_TYPES

    if settings.USE_X_ACCEL_REDIRECT:
        response = HttpResponse(content_type=content_type)
        response["X-Accel-Redirect"] = settings.PROTECTED_MEDIA_INTERNAL_PREFIX + quote(storage_name)
    else:
        full_path = os.path.join(settings.MEDIA_ROOT, storage_name)
        response = FileResponse(open(full_path, "rb"), content_type=content_type)

    response["Content-Disposition"] = _content_disposition(filename, inline)
    response["Cache-Control"] = "private, max-age=3600"
    return response
