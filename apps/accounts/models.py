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
    # Arxiv: hisob saqlanadi (tarix, hisobotlar), lekin tizimga kira olmaydi va
    # shu email bilan qayta ro'yxatdan o'ta olmaydi. Faqat super admin arxivlaydi/chiqaradi.
    is_archived = models.BooleanField("Arxivlangan", default=False, db_index=True)
    archived_at = models.DateTimeField("Arxivlangan vaqt", null=True, blank=True)

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

    def archive(self):
        """Arxivlash: kirishni yopadi va barcha ochiq sessiyalarni (refresh token) bekor qiladi.
        Access token ham darhol ishlamay qoladi — SimpleJWT har so'rovda is_active ni tekshiradi."""
        from django.utils import timezone
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

        self.is_archived = True
        self.is_active = False
        self.archived_at = timezone.now()
        self.save(update_fields=["is_archived", "is_active", "archived_at"])
        for token in OutstandingToken.objects.filter(user=self):
            BlacklistedToken.objects.get_or_create(token=token)

    def unarchive(self):
        self.is_archived = False
        self.is_active = True
        self.archived_at = None
        self.save(update_fields=["is_archived", "is_active", "archived_at"])

    def deletion_impact(self):
        """O'chirilganda u bilan birga butunlay o'chadigan yozuvlar: [{"name", "count"}].
        Django Collector — haqiqiy CASCADE zanjiri (masalan hisobot rasmlari ham) hisoblanadi."""
        from django.db.models.deletion import Collector

        collector = Collector(using=self._state.db or "default")
        collector.collect([self])
        counts = {}
        for model, instances in collector.data.items():
            if model is type(self):
                continue
            counts[model] = counts.get(model, 0) + len(instances)
        for qs in collector.fast_deletes:
            n = qs.count()
            if n:
                counts[qs.model] = counts.get(qs.model, 0) + n
        return sorted(
            ({"name": str(m._meta.verbose_name_plural), "count": c} for m, c in counts.items() if c),
            key=lambda row: -row["count"],
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
        return self.is_staff or self.is_superuser or self.role_assignments.filter(
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

    def is_scientific_council_secretary(self):
        return self.role_assignments.filter(
            role=UserRoleAssignment.Role.SCIENTIFIC_COUNCIL_SECRETARY, is_active=True
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
        SCIENTIFIC_COUNCIL_SECRETARY = "SCIENTIFIC_COUNCIL_SECRETARY", "Ilmiy kengash kotibi"
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
    # ── Yangi maydonlar (moslashuvchan rol tizimi) ───────────────
    # Admin o'zi kiritadigan lavozim nomi (masalan "Rektor", "Filial direktori")
    custom_role_name = models.CharField(max_length=100, blank=True, default="")
    # Foydalanuvchiga topshiriq yaratish huquqi
    can_create_tasks = models.BooleanField(default=False)
    # Shu bo'lim/kafedradagi boshliqmi yoki xodimmi
    is_head = models.BooleanField(default=False)
    # Rahbarlik darajasi
    is_branch_leader = models.BooleanField(default=False)    # filial rahbari
    is_institute_leader = models.BooleanField(default=False) # institut/tashkilot rahbari

    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="assigned_roles"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol biriktiruvi"
        verbose_name_plural = "Rol biriktiruvilari"
        # unique_together olib tashlandi — moslashuvchan rol tizimi

    def __str__(self):
        name = self.custom_role_name or self.get_role_display()
        return f"{self.user.email} — {name}"
