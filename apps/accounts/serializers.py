from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, APIException
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .models import User, UserRoleAssignment

ACCOUNT_PENDING_CODE = "account_pending"
ACCOUNT_PENDING_MESSAGE = (
    "Hisobingiz faol emas. Yangi ro'yxatdan o'tgan bo'lsangiz, "
    "administrator hisobingizni faollashtirishini kuting."
)


class LoginLocked(APIException):
    status_code = 429
    default_code = "login_locked"


class LoginSerializer(TokenObtainPairSerializer):
    """Standart JWT login + nofaol (admin tasdig'ini kutayotgan) hisob uchun aniq xabar.
    Xabar faqat parol TO'G'RI bo'lganda beriladi — aks holda standart xato
    (email mavjudligini oshkor qilmaslik uchun)."""

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            # Muvaffaqiyatsiz urinish audit'ga authenticate() → user_login_failed signali orqali yoziladi
            # django-axes: email bloklangan (5 noto'g'ri urinish) — avval shuni tekshir,
            # aks holda quyidagi parol tekshiruvi blokni chetlab o'tishga imkon beradi
            request = self.context.get("request")
            if getattr(request, "axes_locked_out", False):
                from django.conf import settings
                minutes = int(settings.AXES_COOLOFF_TIME.total_seconds() // 60)
                raise LoginLocked(
                    {"detail": f"Juda ko'p noto'g'ri urinish. {minutes} daqiqadan keyin qayta urinib ko'ring.",
                     "code": "login_locked"}
                )
            user = User.objects.filter(email=attrs.get(self.username_field)).first()
            if user and not user.is_active and user.check_password(attrs.get("password", "")):
                raise AuthenticationFailed(
                    {"detail": ACCOUNT_PENDING_MESSAGE, "code": ACCOUNT_PENDING_CODE}
                )
            raise
        from apps.core.audit import audit
        audit("login_success", self.context.get("request"), user=self.user, via="api")
        return data


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "password", "password2"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Parollar mos kelmadi"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        # Yangi hisob nofaol — super admin UsersPage dan faollashtiradi (pentest K3)
        return User.objects.create_user(**validated_data, is_active=False)


class UserProfileSerializer(serializers.ModelSerializer):
    full_name    = serializers.CharField(read_only=True)
    roles        = serializers.SerializerMethodField()
    is_staff     = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "phone",
            "full_name", "is_staff", "is_superuser", "date_joined", "roles", "has_password",
        ]
        read_only_fields = ["id", "email", "date_joined", "is_staff", "is_superuser", "has_password"]

    def get_has_password(self, obj):
        # Bo'sh satr ("") yoki unusable password ("!...") — ikkalasi ham False
        return bool(obj.password) and obj.has_usable_password()

    def get_roles(self, obj):
        return RoleAssignmentSerializer(
            obj.role_assignments.filter(is_active=True).select_related(
                "organization", "department", "chair"
            ),
            many=True,
        ).data


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "first_name", "last_name", "is_active", "roles"]

    def get_roles(self, obj):
        return RoleAssignmentSerializer(
            obj.role_assignments.filter(is_active=True).select_related(
                "organization", "department", "chair"
            ),
            many=True,
        ).data


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_display      = serializers.CharField(source="get_role_display", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name   = serializers.CharField(source="department.name",   read_only=True)
    department_type   = serializers.CharField(source="department.dept_type", read_only=True)
    chair_name        = serializers.CharField(source="chair.name",        read_only=True)
    # can_create_tasks: assignment darajasi YOKI bo'lim darajasi
    can_create_tasks  = serializers.SerializerMethodField()

    class Meta:
        model = UserRoleAssignment
        fields = [
            "id", "role", "role_display", "custom_role_name",
            "organization", "organization_name",
            "department", "department_name", "department_type", "can_create_tasks",
            "chair", "chair_name",
            "is_head", "is_branch_leader", "is_institute_leader",
            "is_active", "assigned_at",
        ]

    def get_can_create_tasks(self, obj):
        # Assignment darajasi ustunlik qiladi, keyin bo'lim darajasi
        if obj.can_create_tasks:
            return True
        if obj.department and obj.department.can_create_tasks:
            return True
        return False


class UserBasicSerializer(serializers.ModelSerializer):
    """Task ijrochi tanlash uchun minimal foydalanuvchi ma'lumoti."""
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "first_name", "last_name",
                  "department_name", "role_display"]

    def get_department_name(self, obj):
        assignments = (
            obj.role_assignments
            .filter(is_active=True, department__isnull=False)
            .select_related("department")
        )
        names = [a.department.name for a in assignments if a.department]
        return ", ".join(names) if names else None

    def get_role_display(self, obj):
        assignments = (
            obj.role_assignments
            .filter(is_active=True)
        )
        labels = [
            a.custom_role_name or a.get_role_display()
            for a in assignments
        ]
        if not labels:
            return None
        return ", ".join(labels)


class AssignRoleSerializer(serializers.ModelSerializer):
    # role ixtiyoriy — default EMPLOYEE (backend compat uchun)
    role = serializers.ChoiceField(
        choices=UserRoleAssignment.Role.choices,
        default=UserRoleAssignment.Role.EMPLOYEE,
        required=False,
    )

    class Meta:
        model = UserRoleAssignment
        fields = [
            "role", "organization", "department", "chair",
            "custom_role_name", "can_create_tasks", "is_head",
            "is_branch_leader", "is_institute_leader",
        ]

    def validate(self, attrs):
        # Bo'lim/kafedra endi ixtiyoriy — hech qanday majburiy tekshiruv yo'q
        return attrs
