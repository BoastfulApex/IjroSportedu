from django.contrib import admin
from .models import WorkPlan, WorkPlanItem, DailyReport, WeeklyReport, WeeklyReportExtra


class WorkPlanItemInline(admin.TabularInline):
    model = WorkPlanItem
    extra = 0


@admin.register(WorkPlan)
class WorkPlanAdmin(admin.ModelAdmin):
    list_display  = ["department", "year", "title", "created_by"]
    list_filter   = ["year", "department"]
    inlines       = [WorkPlanItemInline]


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ["author", "department", "date", "is_outside_plan"]
    list_filter  = ["date", "department", "is_outside_plan"]


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ["department", "year", "week_number", "week_start", "week_end"]
    list_filter  = ["year", "department"]
