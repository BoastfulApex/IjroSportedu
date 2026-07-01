"""
python manage.py generate_test_token

Birinchi super admindan 1 yillik JWT token yaratadi va
frontend/tests/.env.test fayliga yozadi.

Ishlatish:
    python manage.py generate_test_token
    python manage.py generate_test_token --email=admin@example.com
    python manage.py generate_test_token --days=365
"""

from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from rest_framework_simplejwt.tokens import RefreshToken


class Command(BaseCommand):
    help = "Test uchun 1 yillik JWT access token yaratadi"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, default=None,
                            help="Foydalanuvchi email (default: birinchi superuser)")
        parser.add_argument("--days",  type=int, default=365,
                            help="Token amal qilish muddati (kun, default: 365)")
        parser.add_argument("--write", action="store_true",
                            help="tests/.env.test fayliga avtomatik yozish")

    def handle(self, *args, **options):
        from apps.accounts.models import User

        # Foydalanuvchini topish
        email = options["email"]
        if email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise CommandError(f"Foydalanuvchi topilmadi: {email}")
        else:
            user = (
                User.objects.filter(is_superuser=True, is_active=True).first()
                or User.objects.filter(is_staff=True, is_active=True).first()
                or User.objects.filter(is_active=True).first()
            )
            if not user:
                raise CommandError("Hech qanday faol foydalanuvchi topilmadi")

        # Token yaratish
        days = options["days"]
        refresh = RefreshToken.for_user(user)
        refresh.set_exp(lifetime=timedelta(days=days))
        access = refresh.access_token
        access.set_exp(lifetime=timedelta(days=days))
        access_token = str(access)

        self.stdout.write(self.style.SUCCESS(
            f"\nFoydalanuvchi : {user.email}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Muddat        : {days} kun"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Token         : {access_token[:60]}..."
        ))

        # .env.test fayliga yozish
        env_path = Path(__file__).resolve().parents[7] / "FrontEnd" / "JiraSported" / "tests" / ".env.test"
        # Agar topilmasa, faqat chiqarish
        if options["write"] or env_path.exists():
            self._write_env(env_path, user, access_token, days)
        else:
            self.stdout.write(
                "\nQuyidagini tests/.env.test fayliga qo'shing:\n"
            )
            self._print_env(user, access_token, days)

    def _write_env(self, env_path, user, token, days):
        content = (
            f"# JiraSported API Test Konfiguratsiyasi\n"
            f"# Token {days} kun amal qiladi\n"
            f"# Yangilash: python manage.py generate_test_token\n\n"
            f"API_URL=https://api-ijro.sportedu.uz\n"
            f"TEST_EMAIL={user.email}\n"
            f"TEST_TOKEN={token}\n"
        )
        env_path.write_text(content, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"\nOK: {env_path} fayliga yozildi"))

    def _print_env(self, user, token, days):
        self.stdout.write(
            f"API_URL=https://api-ijro.sportedu.uz\n"
            f"TEST_EMAIL={user.email}\n"
            f"TEST_TOKEN={token}\n"
        )
