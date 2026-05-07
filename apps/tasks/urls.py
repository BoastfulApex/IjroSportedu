from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, MeetingViewSet, RecurringMeetingItemViewSet

router = DefaultRouter()
router.register("", TaskViewSet, basename="tasks")

meeting_router = DefaultRouter()
meeting_router.register("", MeetingViewSet, basename="meetings")

recurring_router = DefaultRouter()
recurring_router.register("", RecurringMeetingItemViewSet, basename="recurring")

urlpatterns = [
    path("meetings/", include(meeting_router.urls)),
    path("recurring/", include(recurring_router.urls)),
    path("", include(router.urls)),
]
