"""Audit log — xavfsizlik uchun muhim amallar (kim, qachon, qaysi IP'dan, nima qildi).

Yoziladigan hodisalar:
  login_success / login_failed  — API (JWT), Google va Django admin orqali kirish
  logout, user_registered
  user_activated / user_deactivated, role_assigned / role_removed
  admin_add / admin_change / admin_delete — Django admin paneldagi o'zgarishlar

Loglar `audit` loggeriga yoziladi (settings: LOGGING). Production'da gunicorn stderr → journald:
    journalctl -u ijrosportedu.service | grep AUDIT
`AUDIT_LOG_FILE` berilsa — qo'shimcha ravishda aylanuvchi faylga ham yoziladi.
Parol va tokenlar hech qachon yozilmaydi.
"""
import logging

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

from .middleware import get_client_ip

logger = logging.getLogger("audit")

_ADMIN_ACTIONS = {ADDITION: "admin_add", CHANGE: "admin_change", DELETION: "admin_delete"}


def _clean(value):
    """Foydalanuvchi kiritgan qiymat log qatorini buzmasin (yangi qator / qo'shtirnoq injeksiyasi)."""
    text = str(value).replace("\r", " ").replace("\n", " ").replace('"', "'")
    return text[:200]


def _actor(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return "-"
    return f"{user.pk}:{user.email}"


def audit(event, request=None, user=None, **fields):
    """Bitta audit yozuvi. `user` — amalni bajargan (berilmasa request.user)."""
    if user is None and request is not None:
        user = getattr(request, "user", None)
    parts = [f"event={event}", f"actor={_clean(_actor(user))}",
             f"ip={get_client_ip(request) if request is not None else '-'}"]
    parts += [f'{key}="{_clean(val)}"' for key, val in fields.items()]
    logger.info("AUDIT %s", " ".join(parts))


@receiver(user_login_failed, dispatch_uid="audit_login_failed")
def _on_login_failed(sender, credentials, request=None, **kwargs):
    # authenticate() bu signalni API (JWT) va admin login'da ham yuboradi; parol tozalangan bo'ladi
    login = credentials.get("email") or credentials.get("username") or "-"
    reason = "locked" if getattr(request, "axes_locked_out", False) else "bad_credentials"
    audit("login_failed", request, login=login, reason=reason,
          via="admin" if _is_admin_request(request) else "api")


@receiver(user_logged_in, dispatch_uid="audit_admin_login")
def _on_logged_in(sender, request, user, **kwargs):
    # JWT login bu signalni yubormaydi (LoginSerializer o'zi yozadi) — bu asosan Django admin
    audit("login_success", request, user=user, via="admin" if _is_admin_request(request) else "session")


@receiver(post_save, sender=LogEntry, dispatch_uid="audit_admin_change")
def _on_admin_change(sender, instance, created, **kwargs):
    if not created:
        return
    audit(_ADMIN_ACTIONS.get(instance.action_flag, "admin_action"), user=instance.user,
          model=instance.content_type.model if instance.content_type_id else "-",
          object_id=instance.object_id or "-", object=instance.object_repr,
          change=instance.get_change_message())


def _is_admin_request(request):
    from django.conf import settings
    admin_url = (getattr(settings, "ADMIN_URL", "") or "").strip("/")
    return bool(request is not None and admin_url and request.path.startswith(f"/{admin_url}/"))
