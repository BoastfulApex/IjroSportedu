from django.contrib import admin
from .models import Organization, Department, Chair


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "org_type", "parent", "is_active"]
    list_filter = ["org_type", "is_active"]
    search_fields = ["name"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "dept_type", "can_create_tasks", "is_active"]
    list_filter = ["dept_type", "can_create_tasks", "is_active"]
    search_fields = ["name"]


@admin.register(Chair)
class ChairAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "is_active"]
    list_filter = ["organization", "is_active"]
    search_fields = ["name"]
