from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PublicOrganizationViewSet, PublicDepartmentViewSet, PublicChairViewSet

# Bo'limlar routeri — departments/ prefixida
dept_router = DefaultRouter()
dept_router.register("", PublicDepartmentViewSet, basename="departments")

# Kafedralar routeri — chairs/ prefixida
chair_router = DefaultRouter()
chair_router.register("", PublicChairViewSet, basename="chairs")

# Tashkilotlar routeri — asosiy prefix (bo'sh)
org_router = DefaultRouter()
org_router.register("", PublicOrganizationViewSet, basename="organizations")

urlpatterns = [
    path("departments/", include(dept_router.urls)),
    path("chairs/", include(chair_router.urls)),
    path("", include(org_router.urls)),
]
