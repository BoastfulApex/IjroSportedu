from django.db import models
from django.conf import settings
from django.utils import timezone


class Task(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Yaratildi"
        ASSIGNED = "ASSIGNED", "Biriktirildi"
        ACCEPTED = "ACCEPTED", "Qabul qilindi"
        IN_PROGRESS = "IN_PROGRESS", "Jarayonda"
        SUBMITTED = "SUBMITTED", "Topshirildi"
        REVIEWING = "REVIEWING", "Tekshirilmoqda"
        APPROVED = "APPROVED", "Tasdiqlandi"
        RETURNED = "RETURNED", "Qaytarildi"
        CLOSED = "CLOSED", "Yopildi"

    class Priority(models.TextChoices):
        CRITICAL = "CRITICAL", "Kritik"
        HIGH = "HIGH", "Yuqori"
        MEDIUM = "MEDIUM", "O'rta"
        LOW = "LOW", "Past"

    VALID_TRANSITIONS = {
        # To'liq zanjir:
        # CREATED → ACCEPTED → IN_PROGRESS → SUBMITTED → APPROVED → CLOSED
        #                                 ↘ RETURNED ↙  (istalgan bosqichda)
        # SUBMITTED → APPROVED  : target bo'lim boshlig'i tasdiqlaydi
        # APPROVED  → CLOSED    : monitoring bo'lim qabul qilib yopadi
        # APPROVED  → RETURNED  : monitoring bo'lim rad etadi → ijrochiga qaytadi
        # SUBMITTED → RETURNED  : target bo'lim boshlig'i rad etadi → ijrochiga qaytadi
        Status.CREATED:     [Status.ACCEPTED, Status.RETURNED],
        Status.ACCEPTED:    [Status.IN_PROGRESS, Status.RETURNED],
        Status.IN_PROGRESS: [Status.SUBMITTED, Status.RETURNED],
        Status.SUBMITTED:   [Status.APPROVED, Status.RETURNED],
        Status.APPROVED:    [Status.CLOSED, Status.RETURNED],
        Status.RETURNED:    [Status.IN_PROGRESS],
        Status.CLOSED:      [],
        # Eski ma'lumotlar bilan orqaga moslik uchun:
        Status.ASSIGNED:    [Status.ACCEPTED, Status.RETURNED],
        Status.REVIEWING:   [Status.APPROVED, Status.RETURNED],
    }

    title = models.CharField(max_length=500, db_index=True)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM, db_index=True
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.CREATED, db_index=True
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    creating_department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tasks",
    )
    target_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="received_tasks",
        db_index=True,
    )
    target_department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="received_tasks",
    )
    deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    is_overdue = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Topshiriq"
        verbose_name_plural = "Topshiriqlar"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["deadline", "is_overdue"]),
            models.Index(fields=["target_organization", "status"]),
            models.Index(fields=["creating_department", "status"]),
        ]

    def __str__(self):
        return self.title

    def check_overdue(self):
        if self.deadline and self.status not in [self.Status.CLOSED, self.Status.APPROVED]:
            return timezone.now() > self.deadline
        return False

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])


class TaskOrganizationTarget(models.Model):
    """
    Bir topshiriq bir nechta tashkilot/bo'lim/kafedraga biriktirilishi mumkin.
    Birinchi yozuv task.target_organization ga ham mos keladi (backward compat).
    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="org_targets")
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="task_org_targets",
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="task_org_targets",
    )
    chair = models.ForeignKey(
        "organizations.Chair",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="task_org_targets",
    )

    class Meta:
        unique_together = ["task", "organization", "department", "chair"]
        verbose_name = "Topshiriq manzili"
        verbose_name_plural = "Topshiriq manzillari"

    def __str__(self):
        parts = [self.organization.name]
        if self.department:
            parts.append(self.department.name)
        if self.chair:
            parts.append(self.chair.name)
        return f"{self.task.title} → {' / '.join(parts)}"


class TaskAssignee(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignees")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_tasks",
    )
    # Qaysi tashkilot / bo'lim / kafedra nomidan biriktirildi (ko'rsatish uchun)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="task_assignees",
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="task_assignees",
    )
    chair = models.ForeignKey(
        "organizations.Chair",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="task_assignees",
    )
    is_primary = models.BooleanField(default=False, verbose_name="Asosiy ijrochi")
    is_leader  = models.BooleanField(default=False, verbose_name="Rahbar mas'ul")
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="task_assignments_given",
    )

    class Meta:
        verbose_name = "Ijrochi"
        verbose_name_plural = "Ijrochilar"
        unique_together = ["task", "user"]

    def __str__(self):
        return f"{self.task.title} → {self.user.full_name}"


def task_attachment_path(instance, filename):
    return f"task_attachments/{instance.task.id}/{filename}"


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=task_attachment_path)
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ilova"
        verbose_name_plural = "Ilovalar"

    def __str__(self):
        return self.filename


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Izoh"
        verbose_name_plural = "Izohlar"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author.full_name}: {self.content[:50]}"


class TaskHistory(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="history")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="task_actions",
    )
    action = models.CharField(max_length=100)
    field_name = models.CharField(max_length=100, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Tarix"
        verbose_name_plural = "Tarixlar"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.task.title} — {self.action} ({self.timestamp})"
