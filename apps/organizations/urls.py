from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PublicOrganizationViewSet, PublicDepartmentViewSet, ChairViewSet
from rest_framework.permissions import IsAuthenticated

router = DefaultRouter()
router.register("", PublicOrganizationViewSet, basename="organizations")

dept_router = DefaultRouter()
dept_router.register("", PublicDepartmentViewSet, basename="departments")

urlpatterns = [
    path("", include(router.urls)),
    path("departments/", include(dept_router.urls)),
]
