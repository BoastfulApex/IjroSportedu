from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_remove_order_file_orderattachment_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderItemAcknowledgment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("viewed_at", models.DateTimeField(blank=True, null=True, verbose_name="Ko'rgan vaqti")),
                ("accepted_at", models.DateTimeField(blank=True, null=True, verbose_name="Qabul qilgan vaqti")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="acknowledgments", to="orders.orderitem")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_item_acknowledgments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Ko'rish/Qabul holati",
                "verbose_name_plural": "Ko'rish/Qabul holatlari",
            },
        ),
        migrations.AlterUniqueTogether(
            name="orderitemacknowledgment",
            unique_together={("item", "user")},
        ),
    ]
