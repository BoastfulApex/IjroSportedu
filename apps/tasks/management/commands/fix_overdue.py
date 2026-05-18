from django.core.management.base import BaseCommand
from apps.tasks.models import Task


class Command(BaseCommand):
    help = "Barcha tasklarning is_overdue qiymatini qayta hisoblaydi"

    def handle(self, *args, **options):
        tasks = Task.objects.exclude(deadline=None)
        updated = 0
        for task in tasks.iterator():
            correct = task.check_overdue()
            if task.is_overdue != correct:
                Task.objects.filter(pk=task.pk).update(is_overdue=correct)
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"{updated} ta task yangilandi"))
