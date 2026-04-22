from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}".strip() or self.email

    def get_roles(self):
        return self.role_assignments.filter(is_active=True).select_related(
            "organization", "department", "chair"
        )

    def has_role(self, role, organization=None, department=None):
        qs = self.role_assignments.filter(role=role, is_active=True)
        if organization:
            qs = qs.filter(organization=organization)
        if department:
            qs = qs.filter(department=department)
        return qs.exists()

    def is_task_controller(self):
        return self.role_assignments.filter(is_active=True).filter(
            models.Q(role=UserRoleAssignment.Role.TASK_CONTROLLER)
            | models.Q(department__dept_type="TASK_CONTROL")
        ).exists()

    def is_super_admin(self):
        return self.is_staff or self.role_assignments.filter(
            role=UserRoleAssignment.Role.SUPER_ADMIN, is_active=True
        ).exists()

    def is_institute_leader(self):
        return self.role_assignments.filter(
            role=UserRoleAssignment.Role.INSTITUTE_LEADER, is_active=True
        ).exists()

    def is_branch_leader(self):
        return self.role_assignments.filter(
            role=UserRoleAssignment.Role.BRANCH_LEADER, is_active=True
        ).exists()

    def get_report_org_ids(self):
        """
        Foydalanuvchi ko'ra oladigan tashkilot ID lari.
        - Super admin / task controller / institute leader → None (hamma)
        - Branch leader → faqat o'z filialini
        """
        if self.is_super_admin() or self.is_task_controller() or self.is_institute_leader():
            return None  # cheklovsiz
        if self.is_branch_leader():
            return list(
                self.role_assignments.filter(
                    role=UserRoleAssignment.Role.BRANCH_LEADER, is_active=True
                ).exclude(organization=None).values_list("organization_id", flat=True)
            )
        return []


class UserRoleAssignment(models.Model):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        INSTITUTE_LEADER = "INSTITUTE_LEADER", "Institut Rahbari"
        BRANCH_LEADER = "BRANCH_LEADER", "Filial Rahbari"
        DEPT_HEAD = "DEPT_HEAD", "Bo'lim Boshlig'i"
        CHAIR_HEAD = "CHAIR_HEAD", "Kafedra Mudiri"
        TASK_CONTROLLER = "TASK_CONTROLLER", "Topshiriq Nazoratchi"
        EMPLOYEE = "EMPLOYEE", "Xodim"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.CharField(max_length=30, choices=Role.choices, db_index=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="role_assignments",
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="role_assignments",
    )
    chair = models.ForeignKey(
        "organizations.Chair",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="role_assignments",
    )
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="assigned_roles"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol biriktiruvi"
        verbose_name_plural = "Rol biriktiruvilari"
        unique_together = ["user", "role", "organization", "department", "chair"]

    def __str__(self):
        return f"{self.user.email} — {self.get_role_display()}"
