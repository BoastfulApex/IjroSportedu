from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # Yangi maydonlar qo'shish
        migrations.AddField(
            model_name="userroleassignment",
            name="custom_role_name",
            field=models.CharField(max_length=100, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="userroleassignment",
            name="can_create_tasks",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userroleassignment",
            name="is_head",
            field=models.BooleanField(default=False),
        ),
        # Rahbarlik darajasi
        migrations.AddField(
            model_name="userroleassignment",
            name="is_branch_leader",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userroleassignment",
            name="is_institute_leader",
            field=models.BooleanField(default=False),
        ),
        # unique_together cheklovini olib tashlash
        migrations.AlterUniqueTogether(
            name="userroleassignment",
            unique_together=set(),
        ),
    ]
