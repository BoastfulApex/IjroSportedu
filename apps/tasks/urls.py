from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, MeetingViewSet

router = DefaultRouter()
router.register("", TaskViewSet, basename="tasks")

meeting_router = DefaultRouter()
meeting_router.register("", MeetingViewSet, basename="meetings")

urlpatterns = [
    path("", include(router.urls)),
    path("meetings/", include(meeting_router.urls)),
]
