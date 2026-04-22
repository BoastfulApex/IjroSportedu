from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, UserRoleAssignment


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
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "full_name", "is_staff", "date_joined", "roles"]
        read_only_fields = ["id", "email", "date_joined", "is_staff"]

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
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    department_type = serializers.CharField(source="department.dept_type", read_only=True)
    can_create_tasks = serializers.BooleanField(source="department.can_create_tasks", read_only=True)
    chair_name = serializers.CharField(source="chair.name", read_only=True)

    class Meta:
        model = UserRoleAssignment
        fields = [
            "id", "role", "role_display",
            "organization", "organization_name",
            "department", "department_name", "department_type", "can_create_tasks",
            "chair", "chair_name",
            "is_active", "assigned_at",
        ]


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
        assignment = (
            obj.role_assignments
            .filter(is_active=True, department__isnull=False)
            .select_related("department")
            .first()
        )
        return assignment.department.name if assignment else None

    def get_role_display(self, obj):
        assignment = (
            obj.role_assignments
            .filter(is_active=True)
            .first()
        )
        return assignment.get_role_display() if assignment else None


class AssignRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRoleAssignment
        fields = ["role", "organization", "department", "chair"]

    def validate(self, attrs):
        role = attrs.get("role")
        if role == UserRoleAssignment.Role.TASK_CONTROLLER and not attrs.get("department"):
            raise serializers.ValidationError(
                {"department": "TASK_CONTROLLER uchun bo'lim ko'rsatilishi shart"}
            )
        if role == UserRoleAssignment.Role.DEPT_HEAD and not attrs.get("department"):
            raise serializers.ValidationError(
                {"department": "Bo'lim boshlig'i uchun bo'lim ko'rsatilishi shart"}
            )
        return attrs
