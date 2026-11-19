"""django-axes uchun yordamchilar."""


def get_axes_username(request, credentials):
    """Blok kaliti — foydalanuvchi email'i.

    API login (`/api/auth/login/`) email'ni `email` maydonida yuboradi,
    Django admin formasi esa `username` maydonida. Ikkalasi ham bitta
    hisob uchun bitta hisoblagichga tushishi kerak.
    """
    credentials = credentials or {}
    value = credentials.get("email") or credentials.get("username")
    if not value and request is not None:
        post = getattr(request, "POST", None) or {}
        value = post.get("email") or post.get("username")
    return (value or "").strip().lower() or None
