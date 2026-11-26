from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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
    RegisterSerializer, UserProfileSerializer, LoginSerializer,
    UserListSerializer, UserBasicSerializer, RoleAssignmentSerializer, AssignRoleSerializer,
    ACCOUNT_PENDING_CODE, ACCOUNT_PENDING_MESSAGE,
    ACCOUNT_ARCHIVED_CODE, ACCOUNT_ARCHIVED_MESSAGE,
)
from .permissions import IsSuperAdmin, HasActiveRole
from apps.core.audit import audit


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class LogoutView(APIView):
    """Refresh tokenni bekor qiladi (blacklist) — undan keyin u bilan yangi access olib bo'lmaydi.

    Access token muddati tugagan bo'lishi mumkin, shuning uchun autentifikatsiya talab qilinmaydi:
    refresh tokenning o'zi egalik isboti. Javob har doim 205 (token holati oshkor qilinmaydi).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        from rest_framework_simplejwt.exceptions import TokenError
        refresh = request.data.get("refresh")
        if refresh:
            try:
                token = RefreshToken(refresh)
                token.blacklist()
                audit("logout", request, user_id=token.payload.get("user_id", "-"))
            except TokenError:
                pass  # muddati o'tgan / allaqachon bekor qilingan / noto'g'ri — baribir chiqildi
        return Response(status=status.HTTP_205_RESET_CONTENT)


def ensure_position_department(assignment):
    """
    Faqat tashkilotga biriktirilgan (bo'lim/kafedra yo'q) xodim uchun —
    lavozim nomi (custom_role_name) asosida Department topib/yaratib bog'laydi.
    Shunda kunlik/haftalik hisobot va boshqa bo'lim-asosli sahifalar
    qo'shimcha o'zgarishsiz ishlayveradi.
    """
    if assignment.department_id or assignment.chair_id:
        return
    if not assignment.organization_id or not assignment.custom_role_name:
        return
    from apps.organizations.models import Department
    dept, _ = Department.objects.get_or_create(
        organization=assignment.organization,
        name=assignment.custom_role_name,
        defaults={"dept_type": Department.DeptType.REGULAR},
    )
    assignment.department = dept
    assignment.save(update_fields=["department"])


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

            # Arxivlangan hisob Google orqali ham kira olmaydi va qayta yaratilmaydi
            # (email katta-kichik harf farqi bilan ham)
            existing = User.objects.filter(email__iexact=email).first()
            if existing and existing.is_archived:
                audit("login_failed", request, login=email, reason="account_archived", via="google")
                return Response(
                    {"detail": ACCOUNT_ARCHIVED_MESSAGE, "code": ACCOUNT_ARCHIVED_CODE},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user, created = User.objects.get_or_create(
                email=existing.email if existing else email,
                defaults={
                    "first_name": first_name,
                    "last_name":  last_name,
                    # Yangi hisob nofaol — super admin faollashtiradi (pentest K3)
                    "is_active":  False,
                },
            )

            if created:
                # Google orqali yaratilgan user — parol yo'q deb belgilaymiz
                user.set_unusable_password()
                user.save(update_fields=["password"])
                audit("user_registered", request, target=f"{user.pk}:{user.email}", via="google")

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
                audit("login_failed", request, login=email, reason="account_pending", via="google")
                return Response(
                    {"detail": ACCOUNT_PENDING_MESSAGE, "code": ACCOUNT_PENDING_CODE, "is_new": created},
                    status=status.HTTP_403_FORBIDDEN,
                )

            refresh = RefreshToken.for_user(user)
            audit("login_success", request, user=user, via="google")
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
    permission_classes = [IsAuthenticated, HasActiveRole]

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

        # Qidiruv (ism, familiya, email, lavozim bo'yicha)
        if search_param:
            qs = qs.filter(
                Q(first_name__icontains=search_param)
                | Q(last_name__icontains=search_param)
                | Q(email__icontains=search_param)
                | Q(role_assignments__custom_role_name__icontains=search_param,
                    role_assignments__is_active=True)
            ).distinct()

        return qs.prefetch_related(
            "role_assignments__department",
            "role_assignments__organization",
            "role_assignments__chair",
        ).order_by("last_name", "first_name")


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        audit("user_registered", request, target=f"{user.pk}:{user.email}", via="form")
        return Response(
            {"detail": "Ro'yxatdan o'tish muvaffaqiyatli. Administrator hisobingizni faollashtirgach, tizimga kira olasiz."},
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class SetPasswordView(APIView):
    """
    Foydalanuvchi o'z parolini o'rnatadi yoki o'zgartiradi.
    - Google orqali kirgan (parolsiz) foydalanuvchi: faqat new_password + confirm_password
    - Parol mavjud foydalanuvchi: current_password + new_password + confirm_password
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_password     = request.data.get("new_password", "").strip()
        confirm_password = request.data.get("confirm_password", "").strip()
        current_password = request.data.get("current_password", "").strip()

        if len(new_password) < 6:
            return Response({"detail": "Parol kamida 6 ta belgidan iborat bo'lishi kerak"}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"detail": "Parollar mos kelmadi"}, status=status.HTTP_400_BAD_REQUEST)

        # Haqiqiy parol mavjudligini tekshirish (bo'sh satr yoki unusable = parol yo'q)
        has_real_password = bool(user.password) and user.has_usable_password()
        if has_real_password:
            if not current_password:
                return Response({"detail": "Joriy parolni kiriting"}, status=status.HTTP_400_BAD_REQUEST)
            if not user.check_password(current_password):
                return Response({"detail": "Joriy parol noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Parol muvaffaqiyatli o'rnatildi", "has_password": True})


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

    def get_queryset(self):
        qs = super().get_queryset()
        # Ro'yxat: standart — arxivsiz; ?archived=1 — faqat arxivlanganlar.
        # Detail amallar (arxivdan chiqarish, o'chirish) arxivlanganlarni ham topadi.
        if self.action == "list":
            archived = self.request.query_params.get("archived") in ("1", "true")
            qs = qs.filter(is_archived=archived)
        return qs

    def perform_update(self, serializer):
        if serializer.instance.is_archived:
            raise ValidationError({"detail": "Arxivlangan foydalanuvchini o'zgartirib bo'lmaydi. Avval arxivdan chiqaring."})
        user = serializer.save()
        audit("user_updated", self.request, target=f"{user.pk}:{user.email}",
              fields=",".join(sorted(serializer.validated_data)))

    def destroy(self, request, *args, **kwargs):
        if self.get_object().pk == request.user.pk:
            return Response({"detail": "O'zingizni o'chira olmaysiz."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        target = f"{instance.pk}:{instance.email}"
        impact = instance.deletion_impact()
        instance.delete()
        audit("user_deleted", self.request, target=target,
              removed=", ".join(f"{r['name']}={r['count']}" for r in impact) or "-")

    @action(detail=True, methods=["get"], url_path="delete-preview")
    def delete_preview(self, request, pk=None):
        """O'chirishdan oldin: u bilan birga butunlay o'chadigan yozuvlar soni."""
        user = self.get_object()
        return Response({"user": user.full_name, "email": user.email, "items": user.deletion_impact()})

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response({"detail": "O'zingizni arxivlay olmaysiz."}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_archived:
            return Response({"detail": "Foydalanuvchi allaqachon arxivlangan."}, status=status.HTTP_400_BAD_REQUEST)
        user.archive()
        audit("user_archived", request, target=f"{user.pk}:{user.email}")
        return Response(UserListSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="unarchive")
    def unarchive(self, request, pk=None):
        user = self.get_object()
        if not user.is_archived:
            return Response({"detail": "Foydalanuvchi arxivda emas."}, status=status.HTTP_400_BAD_REQUEST)
        user.unarchive()
        audit("user_unarchived", request, target=f"{user.pk}:{user.email}")
        return Response(UserListSerializer(user).data)

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
        ensure_position_department(assignment)
        audit("role_assigned", request, target=f"{user.pk}:{user.email}",
              role=assignment.role, assignment_id=assignment.pk)
        return Response(RoleAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"roles/(?P<role_id>\d+)")
    def remove_role(self, request, pk=None, role_id=None):
        user = self.get_object()
        assignment = get_object_or_404(UserRoleAssignment, id=role_id, user=user)
        role = assignment.role
        assignment.delete()
        audit("role_removed", request, target=f"{user.pk}:{user.email}", role=role, assignment_id=role_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        if user.is_archived:
            return Response({"detail": "Arxivlangan foydalanuvchi. Avval arxivdan chiqaring."},
                            status=status.HTTP_400_BAD_REQUEST)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        audit("user_activated" if user.is_active else "user_deactivated", request,
              target=f"{user.pk}:{user.email}")
        return Response({"is_active": user.is_active})
