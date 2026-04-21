from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserRoleAssignment


class RoleAssignmentInline(admin.TabularInline):
    model = UserRoleAssignment
    fk_name = "user"
    extra = 0
    fields = ["role", "organization", "department", "chair", "is_active"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "full_name", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Shaxsiy ma'lumot", {"fields": ("first_name", "last_name", "phone")}),
        ("Huquqlar", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "first_name", "last_name", "password1", "password2")}),
    )
    inlines = [RoleAssignmentInline]


@admin.register(UserRoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "organization", "department", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["user__email"]
