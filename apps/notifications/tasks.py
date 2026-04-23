from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings


def _create_notification(recipient_id, title, message, notif_type, task_id=None):
    from .models import Notification
    Notification.objects.create(
        recipient_id=recipient_id,
        title=title,
        message=message,
        notif_type=notif_type,
        related_task_id=task_id,
    )


def _send_web_push(user_id: int, title: str, body: str, task_id=None):
    """Foydalanuvchining barcha browser subscriptionlariga push yuboradi."""
    try:
        if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
            return
        from .models import PushSubscription
        from pywebpush import webpush, WebPushException
        import json

        subs = list(PushSubscription.objects.filter(user_id=user_id))
        if not subs:
            return

        payload = json.dumps({
            "title": title,
            "body":  body,
            "url":   f"/tasks/{task_id}" if task_id else "/notifications",
        })

        dead = []
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"},
                )
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    dead.append(sub.id)
        if dead:
            PushSubscription.objects.filter(id__in=dead).delete()
    except Exception:
        pass


@shared_task(bind=True, max_retries=3)
def send_task_assignment_notification(self, task_id, user_id):
    try:
        from apps.tasks.models import Task
        from apps.accounts.models import User
        task = Task.objects.select_related("creator", "target_organization").get(id=task_id)
        user = User.objects.get(id=user_id)

        title = f"Yangi topshiriq: {task.title[:50]}"
        message = (
            f"Sizga yangi topshiriq biriktirildi:\n"
            f"Sarlavha: {task.title}\n"
            f"Ustuvorlik: {task.get_priority_display()}\n"
            f"Muddat: {task.deadline.strftime('%d.%m.%Y %H:%M') if task.deadline else 'Belgilanmagan'}"
        )

        _create_notification(
            user.id, title, message,
            "TASK_ASSIGNED", task_id=task.id,
        )
        _send_web_push(user.id, title, message, task_id=task.id)

        send_mail(
            subject=title,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_status_change_notification(self, task_id, old_status, new_status):
    try:
        from apps.tasks.models import Task
        task = Task.objects.select_related("creator").prefetch_related("assignees__user").get(id=task_id)

        status_labels = dict(Task.Status.choices)
        title = f"Topshiriq holati o'zgardi: {task.title[:40]}"
        message = (
            f"Topshiriq: {task.title}\n"
            f"Eski holat: {status_labels.get(old_status, old_status)}\n"
            f"Yangi holat: {status_labels.get(new_status, new_status)}"
        )

        recipients = set()
        if task.creator:
            recipients.add(task.creator.id)
        for a in task.assignees.all():
            recipients.add(a.user_id)

        for rid in recipients:
            _create_notification(rid, title, message, "TASK_STATUS_CHANGED", task_id=task.id)
            _send_web_push(rid, title, message, task_id=task.id)

        from apps.accounts.models import User
        emails = list(User.objects.filter(id__in=recipients).values_list("email", flat=True))
        if emails:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=emails,
                fail_silently=True,
            )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_comment_notification(self, task_id, comment_id, author_id):
    try:
        from apps.tasks.models import Task, TaskComment
        task = Task.objects.prefetch_related("assignees__user").get(id=task_id)
        comment = TaskComment.objects.select_related("author").get(id=comment_id)

        title = f"Yangi izoh: {task.title[:50]}"
        message = f"{comment.author.full_name}: {comment.content[:200]}"

        recipients = set()
        if task.creator:
            recipients.add(task.creator_id)
        for a in task.assignees.all():
            recipients.add(a.user_id)
        recipients.discard(author_id)

        for rid in recipients:
            _create_notification(rid, title, message, "TASK_COMMENT", task_id=task.id)
            _send_web_push(rid, title, message, task_id=task.id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@shared_task
def check_overdue_tasks():
    from apps.tasks.models import Task
    now = timezone.now()
    active_statuses = [
        Task.Status.CREATED, Task.Status.ASSIGNED, Task.Status.ACCEPTED,
        Task.Status.IN_PROGRESS, Task.Status.SUBMITTED, Task.Status.REVIEWING,
    ]
    overdue_tasks = Task.objects.filter(
        deadline__lt=now, status__in=active_statuses, is_overdue=False
    )
    ids = list(overdue_tasks.values_list("id", flat=True))
    Task.objects.filter(id__in=ids).update(is_overdue=True)
    return f"{len(ids)} ta topshiriq muddati o'tdi deb belgilandi"


@shared_task
def send_deadline_warnings():
    from apps.tasks.models import Task
    from datetime import timedelta
    now = timezone.now()
    warning_time = now + timedelta(hours=24)
    active_statuses = [
        Task.Status.CREATED, Task.Status.ASSIGNED, Task.Status.ACCEPTED,
        Task.Status.IN_PROGRESS,
    ]
    soon_tasks = Task.objects.filter(
        deadline__gte=now, deadline__lte=warning_time,
        status__in=active_statuses,
    ).prefetch_related("assignees__user").select_related("creator")

    for task in soon_tasks:
        title = f"Muddat yaqinlashmoqda: {task.title[:50]}"
        hours_left = int((task.deadline - now).total_seconds() / 3600)
        message = (
            f"Topshiriq: {task.title}\n"
            f"Muddat: {task.deadline.strftime('%d.%m.%Y %H:%M')}\n"
            f"Qolgan vaqt: ~{hours_left} soat"
        )
        recipients = set()
        if task.creator:
            recipients.add(task.creator_id)
        for a in task.assignees.all():
            recipients.add(a.user_id)
        for rid in recipients:
            _create_notification(rid, title, message, "DEADLINE_WARNING", task_id=task.id)
            _send_web_push(rid, title, message, task_id=task.id)
