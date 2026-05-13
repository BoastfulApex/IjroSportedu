from rest_framework import serializers
from .models import (
    WorkPlan, WorkPlanItem,
    DailyReport, DailyReportImage,
    WeeklyReport, WeeklyReportExtra, WeeklyReportExtraImage,
)


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
    items_count      = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = WorkPlan
        fields = [
            "id", "department", "department_name", "year", "title",
            "created_by", "created_by_name", "created_at", "items_count", "items",
        ]
        read_only_fields = ["created_by", "created_at"]


class WorkPlanListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    items_count     = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = WorkPlan
        fields = [
            "id", "department", "department_name", "year", "title",
            "created_by_name", "created_at", "items_count",
        ]


# ── DailyReport ───────────────────────────────────────────────────────────────

class DailyReportImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReportImage
        fields = ["id", "image", "uploaded_at"]


class DailyReportSerializer(serializers.ModelSerializer):
    author_name      = serializers.CharField(source="author.full_name", read_only=True)
    department_name  = serializers.CharField(source="department.name", read_only=True)
    work_plan_item_content = serializers.SerializerMethodField()
    images           = DailyReportImageSerializer(many=True, read_only=True)

    class Meta:
        model = DailyReport
        fields = [
            "id", "department", "department_name",
            "author", "author_name",
            "date", "content",
            "work_plan_item", "work_plan_item_content",
            "is_outside_plan",
            "images", "created_at",
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


class DailyReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = [
            "department", "date", "content",
            "work_plan_item", "is_outside_plan",
        ]

    def validate(self, attrs):
        if not attrs.get("is_outside_plan") and not attrs.get("work_plan_item"):
            raise serializers.ValidationError(
                "Reja bandi yoki 'Rejadan tashqari' belgilanishi kerak"
            )
        return attrs


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
            "created_by_name", "created_at", "images",
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
    work_plan_item_info  = serializers.SerializerMethodField()
    images               = DailyReportImageSerializer(many=True, read_only=True)

    class Meta:
        model = DailyReport
        fields = [
            "id", "date", "author_name", "content",
            "work_plan_item", "work_plan_item_info",
            "is_outside_plan", "images",
        ]

    def get_work_plan_item_info(self, obj):
        if obj.work_plan_item:
            return {
                "id": obj.work_plan_item.id,
                "order_number": obj.work_plan_item.order_number,
                "content": obj.work_plan_item.content[:120],
            }
        return None


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
