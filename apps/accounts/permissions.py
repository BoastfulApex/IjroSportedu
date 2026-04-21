from rest_framework.permissions import BasePermission
from .models import UserRoleAssignment


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_super_admin()
        )


class IsTaskController(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_task_controller()
        )


class IsInstituteLeader(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_institute_leader()
        )


class CanViewAllReports(BasePermission):
    """TASK_CONTROLLER yoki INSTITUTE_LEADER"""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_task_controller() or request.user.is_institute_leader() or request.user.is_super_admin()


class CanCreateTask(BasePermission):
    """Faqat TASK_CONTROL bo'lim xodimlari yoki can_create_tasks=True bo'limi xodimlari"""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_super_admin() or request.user.is_task_controller():
            return True
        return UserRoleAssignment.objects.filter(
            user=request.user,
            is_active=True,
            department__can_create_tasks=True,
        ).exists()


class CanAssignCrossBranch(BasePermission):
    """Faqat TASK_CONTROL bo'lim xodimlari"""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_super_admin():
            return True
        return UserRoleAssignment.objects.filter(
            user=request.user,
            is_active=True,
            department__can_assign_cross_branch=True,
        ).exists()


class IsTaskRelated(BasePermission):
    """Task bilan bog'liq foydalanuvchi (creator, assignee, task controller)"""
    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_super_admin() or request.user.is_task_controller():
            return True
        if obj.creator == request.user:
            return True
        return obj.assignees.filter(user=request.user).exists()
