from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotifType(models.TextChoices):
        TASK_ASSIGNED = "TASK_ASSIGNED", "Topshiriq biriktirildi"
        TASK_STATUS_CHANGED = "TASK_STATUS_CHANGED", "Status o'zgardi"
        TASK_COMMENT = "TASK_COMMENT", "Yangi izoh"
        DEADLINE_WARNING = "DEADLINE_WARNING", "Muddat ogohlantirishи"
        TASK_OVERDUE = "TASK_OVERDUE", "Muddati o'tdi"
        TASK_APPROVED = "TASK_APPROVED", "Topshiriq tasdiqlandi"
        TASK_RETURNED = "TASK_RETURNED", "Topshiriq qaytarildi"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notif_type = models.CharField(max_length=30, choices=NotifType.choices, db_index=True)
    related_task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Xabarnoma"
        verbose_name_plural = "Xabarnomalar"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self):
        return f"{self.recipient.email} — {self.title}"
