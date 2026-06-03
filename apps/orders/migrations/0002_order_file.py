from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="orders/files/", verbose_name="Buyruq hujjati"),
        ),
    ]
