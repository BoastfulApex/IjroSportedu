from django.db import models
from django.conf import settings


class Order(models.Model):
    """Buyruq — raqam, sana, sarlavha va bandlardan iborat."""

    class OrderType(models.TextChoices):
        REKTORAT      = "REKTORAT",      "Rektorat buyrug'i"
        ILMIY_KENGASH = "ILMIY_KENGASH", "Ilmiy kengash buyrug'i"
        ICHKI         = "ICHKI",         "Ichki buyruq"

    number      = models.CharField(max_length=50, verbose_name="Buyruq raqami", db_index=True)
    title       = models.CharField(max_length=500, verbose_name="Sarlavha")
    date        = models.DateField(verbose_name="Sana", db_index=True)
    description = models.TextField(blank=True, verbose_name="Tavsif")
    order_type  = models.CharField(
        max_length=30,
        choices=OrderType.choices,
        default=OrderType.REKTORAT,
        verbose_name="Buyruq turi",
        db_index=True,
    )
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_orders",
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False, verbose_name="Topshiriqlar yaratilganmi")

    class Meta:
        verbose_name = "Buyruq"
        verbose_name_plural = "Buyruqlar"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"№{self.number} — {self.title} ({self.date})"


class OrderItem(models.Model):
    """Buyruq bandi — ijro uchun (task yaratadi) yoki kelishish uchun."""

    class ItemType(models.TextChoices):
        IJRO      = "IJRO",      "Ijro uchun"
        KELISHISH = "KELISHISH", "Kelishish uchun"
        MALUMOT   = "MALUMOT",   "Ma'lumot uchun"

    order       = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    band_number = models.PositiveIntegerField(verbose_name="Band raqami")
    content     = models.TextField(verbose_name="Topshiriq mazmuni")
    item_type   = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.IJRO,
        verbose_name="Band turi",
    )
    deadline    = models.DateTimeField(null=True, blank=True, verbose_name="Muddat")
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="order_item_responsibilities",
        verbose_name="Mas'ul ijrochi",
    )
    task = models.OneToOneField(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="order_item",
        verbose_name="Yaratilgan topshiriq",
    )

    class Meta:
        verbose_name = "Buyruq bandi"
        verbose_name_plural = "Buyruq bandlari"
        ordering = ["band_number"]
        unique_together = [["order", "band_number"]]

    def __str__(self):
        return f"{self.order} — Band {self.band_number}"


class OrderItemApprover(models.Model):
    """Kelishish bandi uchun kelishuvchi."""

    item         = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="approvers")
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="order_item_approvals",
    )
    has_approved = models.BooleanField(default=False, verbose_name="Rozimi?")
    approved_at  = models.DateTimeField(null=True, blank=True, verbose_name="Rozilik vaqti")
    added_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="added_order_approvals",
    )

    class Meta:
        verbose_name = "Kelishuvchi"
        verbose_name_plural = "Kelishuvchilar"
        unique_together = [["item", "user"]]

    def __str__(self):
        return f"{self.item} — {self.user.full_name}"


class OrderAttachment(models.Model):
    """Buyruq ilovasi — bir buyruqda bir nechta fayl bo'lishi mumkin."""

    order       = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="attachments")
    file        = models.FileField(upload_to="orders/attachments/", verbose_name="Fayl")
    original_name = models.CharField(max_length=255, blank=True, verbose_name="Asl fayl nomi")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_order_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buyruq ilovasi"
        verbose_name_plural = "Buyruq ilovalari"
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"{self.order} — {self.original_name or self.file.name}"


class OrderItemAcknowledgment(models.Model):
    """Buyruq bandi ijrochisining ko'rgan/qabul qilgan holati."""

    item        = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="acknowledgments")
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="order_item_acknowledgments",
    )
    viewed_at   = models.DateTimeField(null=True, blank=True, verbose_name="Ko'rgan vaqti")
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Qabul qilgan vaqti")

    class Meta:
        verbose_name = "Ko'rish/Qabul holati"
        verbose_name_plural = "Ko'rish/Qabul holatlari"
        unique_together = [["item", "user"]]

    def __str__(self):
        return f"{self.item} — {self.user.full_name}"
