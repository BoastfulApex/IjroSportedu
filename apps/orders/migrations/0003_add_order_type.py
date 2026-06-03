from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="order_type",
            field=models.CharField(
                choices=[("REKTORAT", "Rektorat buyrug'i"), ("ILMIY_KENGASH", "Ilmiy kengash buyrug'i"), ("ICHKI", "Ichki buyruq")],
                default="REKTORAT",
                db_index=True,
                max_length=30,
                verbose_name="Buyruq turi",
            ),
        ),
    ]
