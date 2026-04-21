from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Task, TaskHistory, TaskAssignee


_task_pre_save_state = {}


@receiver(pre_save, sender=Task)
def capture_task_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Task.objects.get(pk=instance.pk)
            _task_pre_save_state[instance.pk] = {
                "status": old.status,
                "priority": old.priority,
                "deadline": old.deadline,
                "title": old.title,
            }
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def create_task_history(sender, instance, created, **kwargs):
    actor = getattr(instance, "_actor", None)

    if created:
        TaskHistory.objects.create(
            task=instance,
            actor=actor,
            action="Topshiriq yaratildi",
        )
        return

    old_state = _task_pre_save_state.pop(instance.pk, {})

    tracked_fields = {
        "status": ("Status", lambda v: dict(Task.Status.choices).get(v, v)),
        "priority": ("Ustuvorlik", lambda v: dict(Task.Priority.choices).get(v, v)),
        "deadline": ("Muddat", lambda v: str(v) if v else "Belgilanmagan"),
        "title": ("Sarlavha", str),
    }

    for field, (label, formatter) in tracked_fields.items():
        old_val = old_state.get(field)
        new_val = getattr(instance, field)
        if old_val != new_val:
            TaskHistory.objects.create(
                task=instance,
                actor=actor,
                action=f"{label} o'zgartirildi",
                field_name=field,
                old_value=formatter(old_val) if old_val is not None else "",
                new_value=formatter(new_val) if new_val is not None else "",
            )

    # overdue check
    instance.is_overdue = instance.check_overdue()
    if old_state.get("status") == instance.status:
        Task.objects.filter(pk=instance.pk).update(is_overdue=instance.is_overdue)


@receiver(post_save, sender=TaskAssignee)
def log_assignee_added(sender, instance, created, **kwargs):
    if created:
        TaskHistory.objects.create(
            task=instance.task,
            actor=instance.assigned_by,
            action="Ijrochi qo'shildi",
            new_value=instance.user.full_name,
        )
        # Trigger notification async
        from apps.notifications.tasks import send_task_assignment_notification
        send_task_assignment_notification.delay(instance.task.id, instance.user.id)
