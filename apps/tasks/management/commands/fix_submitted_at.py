from django.core.management.base import BaseCommand
from apps.tasks.models import Task, TaskHistory
from django.db.models import F


class Command(BaseCommand):
    help = "submitted_at NULL bo'lgan terminal tasklarga history dan submitted_at to'ldiradi"

    def handle(self, *args, **options):
        terminal = Task.objects.filter(
            submitted_at__isnull=True,
            status__in=["SUBMITTED", "REVIEWING", "APPROVED", "CLOSED"],
        )
        fixed = 0
        for task in terminal:
            hist = (
                TaskHistory.objects
                .filter(task=task, new_value__in=["Topshirildi", "Topshirilmoqda"])
                .order_by("timestamp")
                .first()
            )
            if hist:
                Task.objects.filter(pk=task.pk).update(submitted_at=hist.timestamp)
                fixed += 1
                self.stdout.write(
                    f"  Task {task.pk}: submitted_at = {hist.timestamp}"
                    f"  (deadline: {task.deadline})"
                )

        # submitted_at to'ldirilgandan keyin is_overdue ni qayta hisoblash
        from django.db.models import F as F2
        late = Task.objects.filter(
            submitted_at__isnull=False,
            deadline__isnull=False,
            submitted_at__gt=F2("deadline"),
        )
        late_ids = list(late.values_list("id", flat=True))
        Task.objects.filter(id__in=late_ids).update(is_overdue=True)

        on_time = Task.objects.filter(
            submitted_at__isnull=False,
            deadline__isnull=False,
            submitted_at__lte=F2("deadline"),
        )
        ontime_ids = list(on_time.values_list("id", flat=True))
        Task.objects.filter(id__in=ontime_ids).update(is_overdue=False)

        self.stdout.write(self.style.SUCCESS(
            f"\n{fixed} ta task submitted_at bilan to'ldirildi. "
            f"{len(late_ids)} ta kechikib bajarilgan, "
            f"{len(ontime_ids)} ta o'z vaqtida bajarilgan."
        ))
