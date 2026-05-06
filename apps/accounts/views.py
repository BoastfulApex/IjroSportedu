from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import User, UserRoleAssignment
from .serializers import (
    RegisterSerializer, UserProfileSerializer,
    UserListSerializer, UserBasicSerializer, RoleAssignmentSerializer, AssignRoleSerializer,
)
from .permissions import IsSuperAdmin


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        import traceback
        import logging
        logger = logging.getLogger(__name__)

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

            # Google ba'zan family_name bermaydi — bo'sh string bilan ishlaymiz
            first_name = idinfo.get("given_name", "") or ""
            last_name  = idinfo.get("family_name", "") or ""

            # Agar ism yo'q bo'lsa, email dan chiqaramiz
            if not first_name and not last_name:
                first_name = email.split("@")[0]

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name":  last_name,
                },
            )

            if not created:
                changed = False
                if first_name and not user.first_name:
                    user.first_name = first_name
                    changed = True
                if last_name and not user.last_name:
                    user.last_name = last_name
                    changed = True
                if changed:
                    user.save(update_fields=["first_name", "last_name"])

            if not user.is_active:
                return Response({"error": "Foydalanuvchi bloklangan"}, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)
            return Response({
                "access":  str(refresh.access_token),
                "refresh": str(refresh),
                "is_new":  created,
            })

        except ValueError as e:
            logger.warning("Google token xatosi: %s", e)
            return Response({"error": f"Google token noto'g'ri: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Google auth kutilmagan xato:\n%s", traceback.format_exc())
            return Response({"error": f"Xato: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicUserSearchView(generics.ListAPIView):
    """
    Authenticated foydalanuvchilar uchun xodim/rahbar qidirish.

    Query params:
      - departments : vergul bilan ajratilgan bo'lim IDlari  (1,2,3)
      - chairs      : vergul bilan ajratilgan kafedra IDlari  (1,2,3)
      - organization: bitta tashkilot ID (rahbar qidirish uchun)
      - role        : vergul bilan ajratilgan rollar (BRANCH_LEADER,INSTITUTE_LEADER)
      - search      : ism / familiya / email bo'yicha qidiruv
    """
    serializer_class = UserBasicSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = User.objects.filter(is_active=True)
        params = self.request.query_params

        depts_param  = params.get("departments", "").strip()
        chairs_param = params.get("chairs", "").strip()
        org_param    = params.get("organization", "").strip()
        role_param   = params.get("role", "").strip()

        search_param = params.get("search", "").strip()

        # Kamida bitta filter bo'lishi kerak (search yolg'iz bo'lsa ham qabul)
        if not depts_param and not chairs_param and not org_param and not role_param and not search_param:
            return qs.none()

        # Kafedralar bo'yicha filterlash (kafedra mudiri va xodimlari)
        if chairs_param:
            chair_ids = [int(c) for c in chairs_param.split(",") if c.strip().isdigit()]
            if not chair_ids:
                return qs.none()
            qs = qs.filter(
                role_assignments__chair_id__in=chair_ids,
                role_assignments__is_active=True,
            ).distinct()

        # Bo'limlar bo'yicha filterlash
        elif depts_param:
            dept_ids = [int(d) for d in depts_param.split(",") if d.strip().isdigit()]
            if not dept_ids:
                return qs.none()
            qs = qs.filter(
                role_assignments__department_id__in=dept_ids,
                role_assignments__is_active=True,
            ).distinct()

        # Tashkilot bo'yicha filterlash (rahbar qidirish)
        if org_param and org_param.isdigit():
            qs = qs.filter(
                role_assignments__organization_id=int(org_param),
                role_assignments__is_active=True,
            ).distinct()

        # Rol bo'yicha filterlash
        if role_param:
            roles = [r.strip() for r in role_param.split(",") if r.strip()]
            if roles:
                qs = qs.filter(
                    role_assignments__role__in=roles,
                    role_assignments__is_active=True,
                ).distinct()

        # Qidiruv (ism, familiya, email bo'yicha)
        if search_param:
            qs = qs.filter(
                Q(first_name__icontains=search_param)
                | Q(last_name__icontains=search_param)
                | Q(email__icontains=search_param)
            )

        return qs.prefetch_related(
            "role_assignments__department"
        ).order_by("last_name", "first_name")


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
