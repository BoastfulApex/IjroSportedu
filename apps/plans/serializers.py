from rest_framework import serializers
from apps.tasks.models import Task, TaskHistory
from .models import (
    WorkPlan, WorkPlanItem,
    DailyReport, DailyReportImage,
    WeeklyReport, WeeklyReportExtra, WeeklyReportExtraImage,
)

# Kunlik hisobotda avtomatik ko'rsatiladigan topshiriq bosqichlari
TASK_ACTION_LABELS = {
    Task.Status.ACCEPTED.label,
    Task.Status.IN_PROGRESS.label,
    Task.Status.SUBMITTED.label,
}


def get_task_actions(author_id, date):
    """Foydalanuvchi ma'lum bir kunda qaysi topshiriqlar bo'yicha
    qanday amal bajarganini qaytaradi (qabul qildi / boshladi / topshirdi)."""
    qs = (
        TaskHistory.objects.filter(
            actor_id=author_id,
            field_name="status",
            timestamp__date=date,
            new_value__in=TASK_ACTION_LABELS,
        )
        .select_related("task")
        .order_by("timestamp")
    )
    return [
        {
            "id": h.id,
            "task": h.task_id,
            "task_title": h.task.title,
            "status_label": h.new_value,
            "timestamp": h.timestamp,
        }
        for h in qs
    ]


def get_user_position(user, department_id=None):
    """Foydalanuvchining lavozimi — hisobotlar ro'yxatida ko'rsatish uchun.

    Foydalanuvchida bir nechta rol bo'lishi mumkin — shu hisobot qaysi bo'limga
    tegishli bo'lsa, o'sha bo'limdagi lavozim ustunlik qiladi.
    """
    qs = user.role_assignments.filter(is_active=True)
    assignment = None
    if department_id:
        assignment = qs.filter(department_id=department_id).first()
    if not assignment:
        assignment = qs.first()
    if not assignment:
        return None
    return assignment.custom_role_name or assignment.get_role_display()


# ── WorkPlan ─────────────────────────────────────────────────────────────────

class WorkPlanItemSerializer(serializers.ModelSerializer):
    period_type_display  = serializers.CharField(source="get_period_type_display", read_only=True)
    deadline_month_display = serializers.SerializerMethodField()

    class Meta:
        model = WorkPlanItem
        fields = [
            "id", "order_number", "content",
            "period_type", "period_type_display",
            "deadline_month", "deadline_month_display",
        ]

    def get_deadline_month_display(self, obj):
        if obj.deadline_month:
            months = ["Yanvar","Fevral","Mart","Aprel","May","Iyun",
                      "Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"]
            return months[obj.deadline_month - 1]
        return None


class WorkPlanSerializer(serializers.ModelSerializer):
    items            = WorkPlanItemSerializer(many=True, read_only=True)
    department_name  = serializers.CharField(source="department.name", read_only=True)
    created_by_name  = serializers.CharField(source="created_by.full_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True, default=None)
    items_count      = serializers.IntegerField(source="items.count", read_only=True)
    status_display   = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WorkPlan
        fields = [
            "id", "department", "department_name", "year", "title",
            "status", "status_display", "reject_reason",
            "approved_by_name", "approved_at",
            "created_by", "created_by_name", "created_at", "items_count", "items",
        ]
        read_only_fields = ["created_by", "created_at", "status", "approved_by", "approved_at", "reject_reason"]


class WorkPlanListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    items_count     = serializers.IntegerField(source="items.count", read_only=True)
    status_display  = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WorkPlan
        fields = [
            "id", "department", "department_name", "year", "title",
            "status", "status_display", "reject_reason",
            "created_by_name", "created_at", "items_count",
        ]


# ── DailyReport ───────────────────────────────────────────────────────────────

class DailyReportImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReportImage
        fields = ["id", "image", "uploaded_at"]


class DailyReportSerializer(serializers.ModelSerializer):
    author_name      = serializers.CharField(source="author.full_name", read_only=True)
    author_position  = serializers.SerializerMethodField()
    department_name  = serializers.CharField(source="department.name", read_only=True)
    work_plan_item_content = serializers.SerializerMethodField()
    images           = DailyReportImageSerializer(many=True, read_only=True)
    task_actions     = serializers.SerializerMethodField()

    class Meta:
        model = DailyReport
        fields = [
            "id", "department", "department_name",
            "author", "author_name", "author_position",
            "date", "content",
            "work_plan_item", "work_plan_item_content",
            "is_outside_plan",
            "images", "created_at", "task_actions",
        ]
        read_only_fields = ["author", "created_at"]

    def get_work_plan_item_content(self, obj):
        if obj.work_plan_item:
            return {
                "id": obj.work_plan_item.id,
                "order_number": obj.work_plan_item.order_number,
                "content": obj.work_plan_item.content[:100],
            }
        return None

    def get_author_position(self, obj):
        return get_user_position(obj.author, obj.department_id)

    def get_task_actions(self, obj):
        return get_task_actions(obj.author_id, obj.date)


class DailyReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = [
            "id", "department", "date", "content",
            "work_plan_item", "is_outside_plan",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "content": {"allow_blank": True, "required": False},
        }


# ── WeeklyReport ──────────────────────────────────────────────────────────────

class WeeklyReportExtraImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyReportExtraImage
        fields = ["id", "image", "uploaded_at"]


class WeeklyReportExtraSerializer(serializers.ModelSerializer):
    images              = WeeklyReportExtraImageSerializer(many=True, read_only=True)
    created_by_name     = serializers.CharField(source="created_by.full_name", read_only=True)
    work_plan_item_info = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyReportExtra
        fields = [
            "id", "content",
            "work_plan_item", "work_plan_item_info",
            "is_outside_plan",
            "created_by", "created_by_name", "created_at", "images",
        ]
        read_only_fields = ["created_by", "created_at"]

    def get_work_plan_item_info(self, obj):
        if obj.work_plan_item:
            return {
                "id": obj.work_plan_item.id,
                "order_number": obj.work_plan_item.order_number,
                "content": obj.work_plan_item.content[:120],
            }
        return None


class DailyReportBriefSerializer(serializers.ModelSerializer):
    """Haftalik hisobot ichida kunlik hisobotlar uchun."""
    author_name          = serializers.CharField(source="author.full_name", read_only=True)
    author_position      = serializers.SerializerMethodField()
    work_plan_item_info  = serializers.SerializerMethodField()
    images               = DailyReportImageSerializer(many=True, read_only=True)
    task_actions         = serializers.SerializerMethodField()

    class Meta:
        model = DailyReport
        fields = [
            "id", "date", "author", "author_name", "author_position", "content",
            "work_plan_item", "work_plan_item_info",
            "is_outside_plan", "images", "task_actions",
        ]
        read_only_fields = ["author"]

    def get_work_plan_item_info(self, obj):
        if obj.work_plan_item:
            return {
                "id": obj.work_plan_item.id,
                "order_number": obj.work_plan_item.order_number,
                "content": obj.work_plan_item.content[:120],
            }
        return None

    def get_author_position(self, obj):
        return get_user_position(obj.author, obj.department_id)

    def get_task_actions(self, obj):
        return get_task_actions(obj.author_id, obj.date)


class WeeklyReportSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    daily_reports   = serializers.SerializerMethodField()
    extras          = WeeklyReportExtraSerializer(many=True, read_only=True)

    class Meta:
        model = WeeklyReport
        fields = [
            "id", "department", "department_name",
            "year", "week_number", "week_start", "week_end",
            "created_at", "daily_reports", "extras",
        ]

    def get_daily_reports(self, obj):
        qs = obj.daily_reports
        return DailyReportBriefSerializer(qs, many=True).data


class WeeklyReportListSerializer(serializers.ModelSerializer):
    department_name      = serializers.CharField(source="department.name", read_only=True)
    daily_reports_count  = serializers.SerializerMethodField()
    extras_count         = serializers.IntegerField(source="extras.count", read_only=True)

    class Meta:
        model = WeeklyReport
        fields = [
            "id", "department", "department_name",
            "year", "week_number", "week_start", "week_end",
            "daily_reports_count", "extras_count", "created_at",
        ]

    def get_daily_reports_count(self, obj):
        return obj.daily_reports.count()
