from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        from . import audit  # noqa: F401 — audit signal qabul qiluvchilarini ro'yxatdan o'tkazadi
