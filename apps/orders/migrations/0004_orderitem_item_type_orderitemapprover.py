from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_add_order_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="item_type",
            field=models.CharField(
                choices=[("IJRO", "Ijro uchun"), ("KELISHISH", "Kelishish uchun")],
                default="IJRO",
                max_length=20,
                verbose_name="Band turi",
            ),
        ),
        migrations.CreateModel(
            name="OrderItemApprover",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("has_approved", models.BooleanField(default=False, verbose_name="Rozimi?")),
                ("approved_at", models.DateTimeField(blank=True, null=True, verbose_name="Rozilik vaqti")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="approvers", to="orders.orderitem")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_item_approvals", to=settings.AUTH_USER_MODEL)),
                ("added_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="added_order_approvals", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Kelishuvchi",
                "verbose_name_plural": "Kelishuvchilar",
                "unique_together": {("item", "user")},
            },
        ),
    ]
