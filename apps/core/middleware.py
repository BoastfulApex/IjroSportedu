import ipaddress
import logging

from django.conf import settings
from django.http import Http404

logger = logging.getLogger(__name__)

_LOCAL = {"127.0.0.1", "::1"}


def _parse_networks(values):
    nets = []
    for v in values:
        v = (v or "").strip()
        if v:
            nets.append(ipaddress.ip_network(v, strict=False))
    return nets


def get_client_ip(request):
    """Haqiqiy mijoz IP'si.

    Zanjir: mijoz → tashqi nginx (TRUSTED_PROXY_IPS) → django-2 nginx → gunicorn (127.0.0.1).
    Har bir nginx X-Forwarded-For OXIRIGA o'z peer IP'sini qo'shadi, shuning uchun
    o'ngdan chapga yurib, ishonchli proksilarni tashlab, birinchi qolgan IP — mijoz.
    Chap tomondagi (mijoz yuborgan) qiymatlarga hech qachon yetib borilmaydi — soxtalashtirib bo'lmaydi.
    """
    remote = request.META.get("REMOTE_ADDR", "")
    if remote not in _LOCAL:
        # So'rov lokal nginx orqali kelmagan — sarlavhalarga ishonilmaydi
        return remote
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    chain = [ip.strip() for ip in xff.split(",") if ip.strip()]
    trusted = set(getattr(settings, "TRUSTED_PROXY_IPS", []))
    for ip in reversed(chain):
        if ip not in trusted:
            return ip
    # Zanjirda faqat proksilar — "mijoz" proksining o'zi (whitelist uni rad etadi)
    return chain[0] if chain else remote


class AdminIPWhitelistMiddleware:
    """Django admin faqat ADMIN_ALLOWED_IPS dan ochiladi; boshqalarga 404 (admin borligi bilinmaydi)."""

    def __init__(self, get_response):
        self.get_response = get_response
        admin_url = (getattr(settings, "ADMIN_URL", "") or "").strip("/")
        self.prefix = f"/{admin_url}/" if admin_url else None
        self.networks = _parse_networks(getattr(settings, "ADMIN_ALLOWED_IPS", []))

    def __call__(self, request):
        if self.prefix and request.path.startswith(self.prefix):
            client_ip = get_client_ip(request)
            if not self._allowed(client_ip):
                logger.warning("Admin'ga ruxsatsiz IP'dan urinish: %s %s", client_ip, request.path)
                raise Http404
        return self.get_response(request)

    def _allowed(self, ip):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if ip in set(getattr(settings, "TRUSTED_PROXY_IPS", [])):
            return False  # proksining o'zi mijoz bo'la olmaydi
        return any(addr in net for net in self.networks)
