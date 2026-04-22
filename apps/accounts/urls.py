from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, MeView, GoogleAuthView, PublicUserSearchView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("google/", GoogleAuthView.as_view(), name="auth-google"),
    # Bo'lim xodimlarini qidirish (task ijrochisi tanlash uchun)
    path("users/search/", PublicUserSearchView.as_view(), name="users-search"),
]
