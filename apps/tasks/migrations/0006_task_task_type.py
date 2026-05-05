from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0005_taskattachment_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("REKTORAT",   "Rektorat topshirig'i"),
                    ("ILMIY",      "Ilmiy kengash topshirig'i"),
                    ("FUNKSIONAL", "Funksional topshiriq"),
                    ("QOSHIMCHA",  "Qo'shimcha topshiriq"),
                ],
                default="FUNKSIONAL",
                db_index=True,
                max_length=15,
            ),
        ),
    ]
