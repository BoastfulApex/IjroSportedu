from rest_framework.routers import DefaultRouter


class NumericIdRouter(DefaultRouter):
    """
    DefaultRouter, lekin detail URL'dagi ID faqat raqam bo'lishi mumkin.

    Standart router `[^/.]+` ishlatadi: `/api/admin/users/export/` kabi mavjud bo'lmagan
    manzil detail marshrutiga tushib, ruxsat tekshiruvidan 403 qaytarardi (skaner buni
    "endpoint bor" deb o'qiydi). Endi bunday manzillar 404 qaytaradi.
    ViewSet o'zi `lookup_value_regex` bersa — o'shasi ishlatiladi.
    """

    def get_lookup_regex(self, viewset, lookup_prefix=""):
        if getattr(viewset, "lookup_value_regex", None) or getattr(viewset, "lookup_value_converter", None):
            return super().get_lookup_regex(viewset, lookup_prefix)
        lookup_field = getattr(viewset, "lookup_field", "pk")
        lookup_url_kwarg = getattr(viewset, "lookup_url_kwarg", None) or lookup_field
        return f"(?P<{lookup_prefix}{lookup_url_kwarg}>[0-9]+)"
