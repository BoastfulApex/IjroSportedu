from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PublicOrganizationViewSet, PublicDepartmentViewSet

# Bo'limlar routeri — departments/ prefixida
dept_router = DefaultRouter()
dept_router.register("", PublicDepartmentViewSet, basename="departments")

# Tashkilotlar routeri — asosiy prefix (bo'sh)
org_router = DefaultRouter()
org_router.register("", PublicOrganizationViewSet, basename="organizations")

urlpatterns = [
    # MUHIM: departments/ avval bo'lishi kerak!
    # Aks holda path("", include(org_router.urls)) hamma URLni tutib qoladi
    # va "departments/" yo'li hech qachon bu routerga yetmaydi.
    path("departments/", include(dept_router.urls)),
    path("", include(org_router.urls)),
]
