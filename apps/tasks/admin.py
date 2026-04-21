from django.contrib import admin
from .models import Task, TaskAssignee, TaskAttachment, TaskComment, TaskHistory


class AssigneeInline(admin.TabularInline):
    model = TaskAssignee
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "priority", "target_organization", "deadline", "is_overdue"]
    list_filter = ["status", "priority", "is_overdue", "target_organization"]
    search_fields = ["title"]
    inlines = [AssigneeInline]


@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    list_display = ["task", "actor", "action", "timestamp"]
    list_filter = ["action"]
    readonly_fields = ["task", "actor", "action", "field_name", "old_value", "new_value", "timestamp"]
