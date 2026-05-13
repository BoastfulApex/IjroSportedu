from django.db import models
from django.conf import settings
from django.utils import timezone


class WorkPlan(models.Model):
    """Bo'limning yillik ish rejasi."""
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.CASCADE,
        related_name="work_plans",
    )
    year = models.IntegerField()
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_work_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["department", "year"]
        ordering = ["-year"]
        verbose_name = "Yillik ish rejasi"
        verbose_name_plural = "Yillik ish rejalari"

    def __str__(self):
        return f"{self.department.name} — {self.year}"


class WorkPlanItem(models.Model):
    """Yillik ish rejasining bir bandi."""

    class PeriodType(models.TextChoices):
        MONTHLY = "MONTHLY", "Oylik"
        YEARLY  = "YEARLY",  "Yil davomida"

    class Status(models.TextChoices):
        PENDING   = "PENDING",   "Kutilmoqda"
        COMPLETED = "COMPLETED", "Bajarildi"

    MONTH_CHOICES = [
        (1, "Yanvar"), (2, "Fevral"), (3, "Mart"),
        (4, "Aprel"), (5, "May"), (6, "Iyun"),
        (7, "Iyul"), (8, "Avgust"), (9, "Sentabr"),
        (10, "Oktabr"), (11, "Noyabr"), (12, "Dekabr"),
    ]

    work_plan    = models.ForeignKey(WorkPlan, on_delete=models.CASCADE, related_name="items")
    order_number = models.IntegerField()
    content      = models.TextField()
    period_type  = models.CharField(max_length=10, choices=PeriodType.choices, default=PeriodType.YEARLY)
    deadline_month = models.IntegerField(choices=MONTH_CHOICES, null=True, blank=True)
    # Status hozir ko'rinmaydi — kelajakda topshiriqlar bo'limi belgilaydi
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["order_number"]
        verbose_name = "Reja bandi"
        verbose_name_plural = "Reja bandlari"

    def __str__(self):
        return f"{self.work_plan} — {self.order_number}. band"


class DailyReport(models.Model):
    """Kunlik ish hisoboti."""
    department     = models.ForeignKey(
        "organizations.Department",
        on_delete=models.CASCADE,
        related_name="daily_reports",
    )
    author         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_reports",
    )
    date           = models.DateField()
    content        = models.TextField()
    work_plan_item = models.ForeignKey(
        WorkPlanItem,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="daily_reports",
    )
    is_outside_plan = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Kunlik hisobot"
        verbose_name_plural = "Kunlik hisobotlar"

    def __str__(self):
        return f"{self.author} — {self.date}"


class DailyReportImage(models.Model):
    """Kunlik hisobotga biriktirilgan rasm."""
    report     = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name="images")
    image      = models.ImageField(upload_to="daily_reports/images/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]


class WeeklyReport(models.Model):
    """Haftalik hisobot — dushanba yaratiladi, avtomatik."""
    department   = models.ForeignKey(
        "organizations.Department",
        on_delete=models.CASCADE,
        related_name="weekly_reports",
    )
    year         = models.IntegerField()
    week_number  = models.IntegerField()   # ISO hafta raqami (1-53)
    week_start   = models.DateField()      # Dushanba
    week_end     = models.DateField()      # Yakshanba
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["department", "year", "week_number"]
        ordering = ["-year", "-week_number"]
        verbose_name = "Haftalik hisobot"
        verbose_name_plural = "Haftalik hisobotlar"

    def __str__(self):
        return f"{self.department.name} — {self.year}/{self.week_number}-hafta"

    @property
    def daily_reports(self):
        return DailyReport.objects.filter(
            department=self.department,
            date__gte=self.week_start,
            date__lte=self.week_end,
        ).select_related("author", "work_plan_item").prefetch_related("images")


class WeeklyReportExtra(models.Model):
    """Haftalik hisobotga qo'shimcha yozilgan band."""
    weekly_report = models.ForeignKey(WeeklyReport, on_delete=models.CASCADE, related_name="extras")
    content       = models.TextField()
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="weekly_report_extras",
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class WeeklyReportExtraImage(models.Model):
    """Qo'shimcha bandga biriktirilgan rasm."""
    extra      = models.ForeignKey(WeeklyReportExtra, on_delete=models.CASCADE, related_name="images")
    image      = models.ImageField(upload_to="weekly_reports/images/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
