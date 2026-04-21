from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, DepartmentViewSet, ChairViewSet
from apps.accounts.views import UserViewSet

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="admin-organizations")
router.register("departments", DepartmentViewSet, basename="admin-departments")
router.register("chairs", ChairViewSet, basename="admin-chairs")
router.register("users", UserViewSet, basename="admin-users")

urlpatterns = [path("", include(router.urls))]
