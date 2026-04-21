from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.shortcuts import get_object_or_404

from .models import User, UserRoleAssignment
from .serializers import (
    RegisterSerializer, UserProfileSerializer,
    UserListSerializer, RoleAssignmentSerializer, AssignRoleSerializer,
)
from .permissions import IsSuperAdmin


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        credential = request.data.get("credential")
        if not credential:
            return Response({"error": "credential maydoni kerak"}, status=status.HTTP_400_BAD_REQUEST)

        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        if not client_id:
            return Response({"error": "Google OAuth sozlanmagan"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            idinfo = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)

            email = idinfo.get("email", "")
            if not email:
                return Response({"error": "Google emailni taqdim etmadi"}, status=status.HTTP_400_BAD_REQUEST)

            if not idinfo.get("email_verified", False):
                return Response({"error": "Email tasdiqlanmagan"}, status=status.HTTP_400_BAD_REQUEST)

            first_name = idinfo.get("given_name", "")
            last_name = idinfo.get("family_name", "")

            user, created = User.objects.get_or_create(
                email=email,
                defaults={"first_name": first_name, "last_name": last_name},
            )

            if not created:
                if first_name and not user.first_name:
                    user.first_name = first_name
                if last_name and not user.last_name:
                    user.last_name = last_name
                user.save(update_fields=["first_name", "last_name"])

            if not user.is_active:
                return Response({"error": "Foydalanuvchi bloklangan"}, status=status.HTTP_403_FORBIDDEN)

            if not user.has_usable_password():
                pass  # Google user — parolsiz ishlaydi

            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "is_new": created,
            })

        except ValueError:
            return Response({"error": "Google token noto'g'ri yoki muddati o'tgan"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "Google autentifikatsiyada xatolik"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"detail": "Ro'yxatdan o'tish muvaffaqiyatli. Admin sizga rol biriktiradi."},
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related(
        "role_assignments__organization",
        "role_assignments__department",
        "role_assignments__chair",
    ).order_by("last_name", "first_name")
    serializer_class = UserListSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["is_active"]
    search_fields = ["email", "first_name", "last_name"]

    @action(detail=True, methods=["post"], url_path="assign-role")
    def assign_role(self, request, pk=None):
        user = self.get_object()
        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = UserRoleAssignment.objects.create(
            user=user,
            assigned_by=request.user,
            **serializer.validated_data,
        )
        return Response(RoleAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"roles/(?P<role_id>\d+)")
    def remove_role(self, request, pk=None, role_id=None):
        user = self.get_object()
        assignment = get_object_or_404(UserRoleAssignment, id=role_id, user=user)
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response({"is_active": user.is_active})
