from django.urls import path
from .views import (
    OverviewReportView, ByOrganizationReportView,
    ByDepartmentReportView, OverdueTasksView, MyTasksView,
)

urlpatterns = [
    path("overview/", OverviewReportView.as_view(), name="report-overview"),
    path("by-organization/", ByOrganizationReportView.as_view(), name="report-by-org"),
    path("by-department/", ByDepartmentReportView.as_view(), name="report-by-dept"),
    path("overdue/", OverdueTasksView.as_view(), name="report-overdue"),
    path("my-tasks/", MyTasksView.as_view(), name="report-my-tasks"),
]
