from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plans", "0003_workplan_approved_at_workplan_approved_by_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dailyreport",
            name="content",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="weeklyreportextra",
            name="content",
            field=models.TextField(blank=True, default=""),
        ),
    ]
