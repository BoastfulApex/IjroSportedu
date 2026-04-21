from django.db import models


class Organization(models.Model):
    class OrgType(models.TextChoices):
        MAIN = "MAIN", "Asosiy Institut"
        BRANCH = "BRANCH", "Filial"

    name = models.CharField(max_length=255, db_index=True)
    short_name = models.CharField(max_length=50, blank=True)
    org_type = models.CharField(max_length=10, choices=OrgType.choices, db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="branches",
    )
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        ordering = ["org_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"],
                name="unique_org_name_per_parent",
            )
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_main(cls):
        return cls.objects.filter(org_type=cls.OrgType.MAIN, is_active=True).first()


class Department(models.Model):
    class DeptType(models.TextChoices):
        REGULAR = "REGULAR", "Oddiy Bo'lim"
        TASK_CONTROL = "TASK_CONTROL", "Topshiriqlar Bo'limi"

    name = models.CharField(max_length=255, db_index=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="departments"
    )
    dept_type = models.CharField(
        max_length=20, choices=DeptType.choices, default=DeptType.REGULAR, db_index=True
    )
    can_create_tasks = models.BooleanField(default=False)
    can_assign_cross_branch = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bo'lim"
        verbose_name_plural = "Bo'limlar"
        ordering = ["organization", "name"]

    def __str__(self):
        return f"{self.name} ({self.organization.short_name or self.organization.name})"

    def save(self, *args, **kwargs):
        if self.dept_type == self.DeptType.TASK_CONTROL:
            self.can_create_tasks = True
            self.can_assign_cross_branch = True
        super().save(*args, **kwargs)


class Chair(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="chairs"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kafedra"
        verbose_name_plural = "Kafedralar"
        ordering = ["department", "name"]

    def __str__(self):
        return f"{self.name} — {self.department.name}"
