"""
Google orqali ro'yxatdan o'tgan va bo'sh parolga ega userlarni tuzatish.
Bir marta ishlatiladi: python manage.py fix_google_passwords
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Google orqali yaratilgan userlardagi bo'sh parolni unusable qilib belgilaydi"

    def handle(self, *args, **options):
        # Paroli bo'sh satr bo'lgan userlarni topamiz
        users = User.objects.filter(password="")
        count = users.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Tuzatish kerak bo'lgan user topilmadi."))
            return

        fixed = 0
        for user in users:
            user.set_unusable_password()
            user.save(update_fields=["password"])
            fixed += 1
            self.stdout.write(f"  Tuzatildi: {user.email}")

        self.stdout.write(self.style.SUCCESS(f"\nJami {fixed} ta user tuzatildi."))
