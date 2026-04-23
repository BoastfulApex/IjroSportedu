from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0004_add_chair_to_task_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="taskattachment",
            name="attachment_type",
            field=models.CharField(
                choices=[("TASK_FILE", "Topshiriq fayli"), ("REPORT_FILE", "Hisobot fayli")],
                default="TASK_FILE",
                db_index=True,
                max_length=15,
            ),
        ),
        migrations.AlterField(
            model_name="taskattachment",
            name="uploaded_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="uploaded_attachments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
