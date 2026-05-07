from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0010_task_meeting_cascade"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. RecurringMeetingItem modeli yaratish
        migrations.CreateModel(
            name="RecurringMeetingItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(verbose_name="Topshiriq mazmuni")),
                ("meeting_type", models.CharField(
                    choices=[("REKTORAT", "Rektorat"), ("ILMIY", "Ilmiy kengash")],
                    db_index=True, max_length=20, verbose_name="Majlis turi",
                )),
                ("valid_year", models.IntegerField(db_index=True, verbose_name="Amal qilish yili")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Faol")),
                ("created_by", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_recurring_items",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Doimiy band",
                "verbose_name_plural": "Doimiy bandlar",
                "ordering": ["created_at"],
            },
        ),
        # 2. MeetingAgendaItem ga recurring_item FK qo'shish
        migrations.AddField(
            model_name="meetingagendaitem",
            name="recurring_item",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="agenda_items",
                to="tasks.recurringmeetingitem",
                verbose_name="Doimiy band manbasi",
            ),
        ),
    ]
