from django.urls import path, include
from apps.core.routers import NumericIdRouter as DefaultRouter
from .views import OrderViewSet

router = DefaultRouter()
router.register("", OrderViewSet, basename="orders")

urlpatterns = [
    path("", include(router.urls)),
]
