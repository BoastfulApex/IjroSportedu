from django.urls import path, include
from apps.core.routers import NumericIdRouter as DefaultRouter
from .views import WorkPlanViewSet, DailyReportViewSet, WeeklyReportViewSet

router = DefaultRouter()
router.register("work-plans",    WorkPlanViewSet,    basename="work-plans")
router.register("daily-reports", DailyReportViewSet, basename="daily-reports")
router.register("weekly-reports", WeeklyReportViewSet, basename="weekly-reports")

urlpatterns = [
    path("", include(router.urls)),
]
