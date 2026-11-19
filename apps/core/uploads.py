"""Yuklanadigan fayllarni tekshirish: hajm, kengaytma va haqiqiy tarkib (magic bytes / Pillow).

Ishlatish (view ichida):
    error = validate_upload(file, kind="document")
    if error:
        return Response({"detail": error}, status=400)
"""
import os

from django.conf import settings

# Ruxsat etilgan kengaytmalar (kichik harfda). HTML, SVG, JS, EXE va h.k. — yo'q.
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
EXCEL_EXT = {".xlsx", ".xls"}
DOCUMENT_EXT = IMAGE_EXT | EXCEL_EXT | {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".odt", ".ods", ".odp",
    ".rtf", ".txt", ".csv", ".zip", ".rar", ".7z",
}
KIND_EXT = {"image": IMAGE_EXT, "excel": EXCEL_EXT, "document": DOCUMENT_EXT}

# Fayl boshidagi imzolar (magic bytes)
_PDF = (b"%PDF",)
_ZIP = (b"PK\x03\x04", b"PK\x05\x06")                       # docx/xlsx/pptx/odt/zip
_OLE = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)                # doc/xls/ppt (eski Office)
MAGIC = {
    ".pdf": _PDF,
    ".docx": _ZIP, ".xlsx": _ZIP, ".pptx": _ZIP, ".odt": _ZIP, ".ods": _ZIP, ".odp": _ZIP, ".zip": _ZIP,
    ".doc": _OLE, ".xls": _OLE, ".ppt": _OLE,
    ".rar": (b"Rar!\x1a\x07",),
    ".7z": (b"7z\xbc\xaf\x27\x1c",),
    ".rtf": (b"{\\rtf",),
}
# Matnli fayllar ichida HTML/skript bo'lmasligi kerak
_TEXT_EXT = {".txt", ".csv"}
_HTML_MARKERS = (b"<html", b"<script", b"<svg", b"<!doctype", b"<iframe", b"<body")


def _head(file, size=2048):
    pos = file.tell() if hasattr(file, "tell") else 0
    file.seek(0)
    data = file.read(size)
    file.seek(pos)
    return data


def _is_valid_image(file):
    from PIL import Image
    try:
        file.seek(0)
        with Image.open(file) as img:
            img.verify()
        return True
    except Exception:
        return False
    finally:
        file.seek(0)


def validate_upload(file, kind="document"):
    """Xato bo'lsa — foydalanuvchiga ko'rsatiladigan o'zbekcha xabar, aks holda None."""
    if file is None:
        return "Fayl yuborilmadi"

    max_size = settings.MAX_UPLOAD_SIZE
    if file.size > max_size:
        return f"Fayl hajmi {max_size // (1024 * 1024)} MB dan oshmasligi kerak ({file.name})"
    if file.size == 0:
        return f"Fayl bo'sh ({file.name})"

    ext = os.path.splitext(file.name or "")[1].lower()
    allowed = KIND_EXT[kind]
    if ext not in allowed:
        return f"Bu turdagi fayl qabul qilinmaydi: {ext or 'kengaytmasiz'}. Ruxsat etilgan: {', '.join(sorted(allowed))}"

    if ext in IMAGE_EXT:
        if not _is_valid_image(file):
            return f"Fayl haqiqiy rasm emas yoki buzilgan ({file.name})"
        return None

    head = _head(file)
    signatures = MAGIC.get(ext)
    if signatures and not head.startswith(signatures):
        return f"Fayl tarkibi kengaytmasiga mos emas ({file.name})"
    if ext in _TEXT_EXT and any(m in head.lower() for m in _HTML_MARKERS):
        return f"Matnli faylda HTML/skript bo'lishi mumkin emas ({file.name})"
    return None


def validate_uploads(files, kind="document"):
    """Bir nechta fayl — birinchi xato xabari yoki None."""
    for f in files:
        error = validate_upload(f, kind)
        if error:
            return error
    return None
