import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("buyruqsportedu")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "check-overdue-tasks-every-hour": {
        "task": "apps.notifications.tasks.check_overdue_tasks",
        "schedule": crontab(minute=0),
    },
    "send-deadline-warnings-every-hour": {
        "task": "apps.notifications.tasks.send_deadline_warnings",
        "schedule": crontab(minute=30),
    },
}
