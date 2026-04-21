from rest_framework import serializers
from .models import Organization, Department, Chair


class OrganizationSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    branches_count = serializers.SerializerMethodField()
    departments_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id", "name", "short_name", "org_type", "parent", "parent_name",
            "address", "is_active", "created_at", "branches_count", "departments_count",
        ]

    def get_branches_count(self, obj):
        return obj.branches.filter(is_active=True).count()

    def get_departments_count(self, obj):
        return obj.departments.filter(is_active=True).count()

    def validate(self, attrs):
        org_type = attrs.get("org_type", getattr(self.instance, "org_type", None))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if org_type == Organization.OrgType.BRANCH and not parent:
            raise serializers.ValidationError({"parent": "Filial uchun asosiy tashkilot ko'rsatilishi shart"})
        if org_type == Organization.OrgType.MAIN and parent:
            raise serializers.ValidationError({"parent": "Asosiy institut uchun parent bo'lmasligi kerak"})
        return attrs


class DepartmentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    chairs_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id", "name", "organization", "organization_name",
            "dept_type", "can_create_tasks", "can_assign_cross_branch",
            "is_active", "created_at", "chairs_count",
        ]

    def get_chairs_count(self, obj):
        return obj.chairs.filter(is_active=True).count()


class ChairSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    organization_name = serializers.CharField(source="department.organization.name", read_only=True)

    class Meta:
        model = Chair
        fields = [
            "id", "name", "department", "department_name",
            "organization_name", "is_active", "created_at",
        ]
