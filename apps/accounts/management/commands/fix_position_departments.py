"""
python manage.py fix_position_departments

Faqat tashkilotga biriktirilgan (bo'lim/kafedra yo'q), lekin lavozim nomi
(custom_role_name) bor bo'lgan mavjud xodimlar uchun — lavozim nomi asosida
Department topib/yaratib bog'laydi. Shundan keyin ular ham Kunlik/Haftalik
hisobot sahifalaridan foydalana oladi.
"""

from django.core.management.base import BaseCommand
from apps.accounts.models import UserRoleAssignment
from apps.accounts.views import ensure_position_department


class Command(BaseCommand):
    help = "Faqat tashkilotga biriktirilgan xodimlarga lavozim nomi asosida Department bog'laydi"

    def handle(self, *args, **options):
        qs = UserRoleAssignment.objects.filter(
            is_active=True,
            department__isnull=True,
            chair__isnull=True,
            organization__isnull=False,
        ).exclude(custom_role_name="")

        fixed = 0
        for assignment in qs:
            ensure_position_department(assignment)
            if assignment.department_id:
                fixed += 1
                self.stdout.write(
                    f"  {assignment.user.email} — \"{assignment.custom_role_name}\" -> {assignment.department.name}"
                )

        self.stdout.write(self.style.SUCCESS(f"\n{fixed} ta xodim lavozim bo'yicha bo'limga bog'landi"))
