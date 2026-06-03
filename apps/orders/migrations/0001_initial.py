from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tasks", "0012_add_submitted_at_to_task"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(db_index=True, max_length=50, verbose_name="Buyruq raqami")),
                ("title", models.CharField(max_length=500, verbose_name="Sarlavha")),
                ("date", models.DateField(db_index=True, verbose_name="Sana")),
                ("description", models.TextField(blank=True, verbose_name="Tavsif")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_confirmed", models.BooleanField(default=False, verbose_name="Topshiriqlar yaratilganmi")),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Buyruq",
                "verbose_name_plural": "Buyruqlar",
                "ordering": ["-date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("band_number", models.PositiveIntegerField(verbose_name="Band raqami")),
                ("content", models.TextField(verbose_name="Topshiriq mazmuni")),
                ("deadline", models.DateTimeField(blank=True, null=True, verbose_name="Muddat")),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="orders.order",
                    ),
                ),
                (
                    "responsible",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="order_item_responsibilities",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Mas'ul ijrochi",
                    ),
                ),
                (
                    "task",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="order_item",
                        to="tasks.task",
                        verbose_name="Yaratilgan topshiriq",
                    ),
                ),
            ],
            options={
                "verbose_name": "Buyruq bandi",
                "verbose_name_plural": "Buyruq bandlari",
                "ordering": ["band_number"],
                "unique_together": {("order", "band_number")},
            },
        ),
    ]
