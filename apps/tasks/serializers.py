from rest_framework import serializers
from django.utils import timezone
from .models import Task, TaskOrganizationTarget, TaskAssignee, TaskAttachment, TaskComment, TaskHistory, Meeting, MeetingAgendaItem
from apps.accounts.serializers import UserListSerializer

ACTIVE_STATUSES = {
    Task.Status.CREATED, Task.Status.ASSIGNED, Task.Status.ACCEPTED,
    Task.Status.IN_PROGRESS, Task.Status.SUBMITTED, Task.Status.REVIEWING,
}


class TaskAssigneeSerializer(serializers.ModelSerializer):
    user_email         = serializers.EmailField(source="user.email",      read_only=True)
    user_full_name     = serializers.CharField(source="user.full_name",   read_only=True)
    organization_name  = serializers.CharField(source="organization.name",read_only=True)
    department_name    = serializers.CharField(source="department.name",  read_only=True)
    chair_name         = serializers.CharField(source="chair.name",       read_only=True)

    class Meta:
        model = TaskAssignee
        fields = [
            "id", "user", "user_email", "user_full_name",
            "organization", "organization_name",
            "department", "department_name",
            "chair", "chair_name",
            "is_primary", "is_leader", "assigned_at",
        ]
        read_only_fields = ["assigned_at"]


class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name  = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email",    read_only=True)
    attachment_type_display = serializers.CharField(
        source="get_attachment_type_display", read_only=True
    )
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TaskAttachment
        fields = [
            "id", "file", "file_url", "filename", "file_size",
            "attachment_type", "attachment_type_display",
            "uploaded_by", "uploaded_by_name", "uploaded_by_email", "uploaded_at",
        ]
        read_only_fields = ["filename", "file_size", "uploaded_by", "uploaded_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = TaskComment
        fields = [
            "id", "author", "author_name", "author_email",
            "content", "created_at", "updated_at", "is_edited",
        ]
        read_only_fields = ["author", "created_at", "updated_at", "is_edited"]


class TaskHistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True)

    class Meta:
        model = TaskHistory
        fields = [
            "id", "actor", "actor_name", "action",
            "field_name", "old_value", "new_value", "timestamp",
        ]


class TaskOrganizationTargetSerializer(serializers.ModelSerializer):
    organization_name  = serializers.CharField(source="organization.name",  read_only=True)
    organization_short = serializers.CharField(source="organization.short_name", read_only=True)
    department_name    = serializers.CharField(source="department.name",    read_only=True)
    chair_name         = serializers.CharField(source="chair.name",         read_only=True)

    class Meta:
        model = TaskOrganizationTarget
        fields = ["id", "organization", "organization_name", "organization_short",
                  "department", "department_name",
                  "chair", "chair_name"]


# ── Topshiriq yaratishda manzil inputi ──────────────────────────
class OrgTargetInputSerializer(serializers.Serializer):
    organization = serializers.IntegerField()
    department   = serializers.IntegerField(required=False, allow_null=True, default=None)
    chair        = serializers.IntegerField(required=False, allow_null=True, default=None)


class TaskListSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.full_name", read_only=True)
    target_organization_name = serializers.CharField(
        source="target_organization.name", read_only=True
    )
    target_department_name = serializers.CharField(
        source="target_department.name", read_only=True
    )
    creating_department_name = serializers.CharField(
        source="creating_department.name", read_only=True
    )
    assignees_count = serializers.SerializerMethodField()
    assignees = TaskAssigneeSerializer(many=True, read_only=True)
    priority_display  = serializers.CharField(source="get_priority_display",  read_only=True)
    status_display    = serializers.CharField(source="get_status_display",    read_only=True)
    task_type_display = serializers.CharField(source="get_task_type_display", read_only=True)
    # is_overdue — bazadagi qiymat emas, har safar real vaqtda hisoblanadi
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id", "title", "priority", "priority_display", "status", "status_display",
            "task_type", "task_type_display",
            "creator", "creator_name", "creating_department", "creating_department_name",
            "target_organization", "target_organization_name",
            "target_department", "target_department_name",
            "deadline", "is_overdue", "created_at", "updated_at",
            "assignees_count", "assignees",
        ]

    def get_assignees_count(self, obj):
        return obj.assignees.count()

    def get_is_overdue(self, obj):
        if not obj.deadline:
            return False
        return obj.deadline < timezone.now() and obj.status in ACTIVE_STATUSES


class TaskDetailSerializer(serializers.ModelSerializer):
    assignees = TaskAssigneeSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    org_targets = TaskOrganizationTargetSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source="creator.full_name", read_only=True)
    target_organization_name = serializers.CharField(
        source="target_organization.name", read_only=True
    )
    target_department_name = serializers.CharField(
        source="target_department.name", read_only=True
    )
    creating_department_name = serializers.CharField(
        source="creating_department.name", read_only=True
    )
    valid_transitions = serializers.SerializerMethodField()
    priority_display  = serializers.CharField(source="get_priority_display",  read_only=True)
    status_display    = serializers.CharField(source="get_status_display",    read_only=True)
    task_type_display = serializers.CharField(source="get_task_type_display", read_only=True)
    is_overdue        = serializers.SerializerMethodField()
    meeting_info      = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "priority", "priority_display",
            "status", "status_display", "valid_transitions",
            "task_type", "task_type_display",
            "creator", "creator_name", "creating_department", "creating_department_name",
            "target_organization", "target_organization_name",
            "target_department", "target_department_name",
            "deadline", "is_overdue", "created_at", "updated_at",
            "assignees", "attachments", "org_targets", "comments_count",
            "meeting_info",
        ]

    def get_meeting_info(self, obj):
        if not obj.meeting_id:
            return None
        m = obj.meeting
        request = self.context.get("request")
        file_url = None
        if m.file:
            file_url = request.build_absolute_uri(m.file.url) if request else m.file.url
        return {
            "id":         m.id,
            "name":       m.name,
            "date":       str(m.date),
            "type_label": m.get_meeting_type_display(),
            "file_url":   file_url,
        }

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_overdue(self, obj):
        if not obj.deadline:
            return False
        return obj.deadline < timezone.now() and obj.status in ACTIVE_STATUSES

    def get_valid_transitions(self, obj):
        return Task.VALID_TRANSITIONS.get(obj.status, [])

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get("request")
        if request and ret.get("attachments"):
            for att in ret["attachments"]:
                if att.get("file"):
                    att["file_url"] = request.build_absolute_uri(att["file"])
        return ret


class TaskCreateSerializer(serializers.ModelSerializer):
    targets = OrgTargetInputSerializer(many=True, write_only=True)
    deadline = serializers.DateTimeField(
        required=False,
        allow_null=True,
        input_formats=[
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "iso-8601",
        ],
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "title", "description", "priority", "task_type",
            "targets",   # ← bir nechta tashkilot manzillari
            "deadline",
        ]
        read_only_fields = ["id"]

    def validate_targets(self, value):
        if not value:
            raise serializers.ValidationError("Kamida bitta tashkilot tanlang")
        return value

    def validate_deadline(self, value):
        if value is None:
            return value
        if timezone.is_naive(value):
            value = timezone.make_aware(value)
        if value < timezone.now():
            raise serializers.ValidationError("Muddat o'tgan vaqtga belgilanishi mumkin emas")
        return value


class TaskStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        task = self.context.get("task")
        if task and not task.can_transition_to(value):
            raise serializers.ValidationError(
                f"'{task.get_status_display()}' dan '{Task.Status(value).label}' ga o'tish mumkin emas"
            )
        return value


# ── Majlis serializers ──────────────────────────────────────────────────────

class MeetingAgendaItemSerializer(serializers.ModelSerializer):
    task_id       = serializers.IntegerField(source="task.id",       read_only=True)
    task_status   = serializers.CharField(source="task.status",      read_only=True)
    task_title    = serializers.CharField(source="task.title",       read_only=True)
    task_deadline = serializers.DateTimeField(source="task.deadline", read_only=True)
    task_priority = serializers.CharField(source="task.priority",    read_only=True)
    task_assignees = serializers.SerializerMethodField()
    is_created     = serializers.SerializerMethodField()

    class Meta:
        model  = MeetingAgendaItem
        fields = [
            "id", "band_number", "content",
            "task_id", "task_title", "task_status", "task_deadline", "task_priority",
            "task_assignees", "is_created",
        ]

    def get_is_created(self, obj):
        return obj.task_id is not None

    def get_task_assignees(self, obj):
        if not obj.task_id:
            return []
        return [
            {
                "user_id":       a.user_id,
                "full_name":     a.user.full_name,
                "is_primary":    a.is_primary,
            }
            for a in obj.task.assignees.select_related("user").all()
        ]


class MeetingSerializer(serializers.ModelSerializer):
    items              = MeetingAgendaItemSerializer(many=True, read_only=True)
    created_by_name    = serializers.CharField(source="created_by.full_name", read_only=True)
    meeting_type_label = serializers.CharField(source="get_meeting_type_display", read_only=True)
    items_count        = serializers.IntegerField(source="items.count", read_only=True)
    created_count      = serializers.SerializerMethodField()
    file_url           = serializers.SerializerMethodField()

    class Meta:
        model  = Meeting
        fields = [
            "id", "name", "meeting_type", "meeting_type_label",
            "date", "is_confirmed",
            "created_by", "created_by_name",
            "created_at", "items_count", "created_count", "items",
            "file_url",
        ]
        read_only_fields = ["created_by", "is_confirmed", "created_at"]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url

    def get_created_count(self, obj):
        return obj.items.filter(task__isnull=False).count()


class MeetingListSerializer(serializers.ModelSerializer):
    """Ro'yxat uchun — items yuklamas"""
    created_by_name    = serializers.CharField(source="created_by.full_name", read_only=True)
    meeting_type_label = serializers.CharField(source="get_meeting_type_display", read_only=True)
    items_count        = serializers.IntegerField(source="items.count", read_only=True)
    created_count      = serializers.SerializerMethodField()
    file_url           = serializers.SerializerMethodField()

    class Meta:
        model  = Meeting
        fields = [
            "id", "name", "meeting_type", "meeting_type_label",
            "date", "is_confirmed",
            "created_by_name", "created_at", "items_count", "created_count",
            "file_url",
        ]

    def get_created_count(self, obj):
        return obj.items.filter(task__isnull=False).count()

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url
