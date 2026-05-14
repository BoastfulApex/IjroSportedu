import datetime
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from django.utils import timezone

from .models import (
    WorkPlan, WorkPlanItem,
    DailyReport, DailyReportImage,
    WeeklyReport, WeeklyReportExtra, WeeklyReportExtraImage,
)
from .serializers import (
    WorkPlanSerializer, WorkPlanListSerializer, WorkPlanItemSerializer,
    DailyReportSerializer, DailyReportCreateSerializer,
    WeeklyReportSerializer, WeeklyReportListSerializer,
    WeeklyReportExtraSerializer,
    DailyReportImageSerializer, WeeklyReportExtraImageSerializer,
)


def get_user_dept_ids(user):
    return list(
        user.role_assignments.filter(is_active=True)
        .exclude(department=None)
        .values_list("department_id", flat=True)
    )


def can_view_all(user):
    return user.is_super_admin() or user.is_task_controller() or user.is_institute_leader()


# ── WorkPlan ─────────────────────────────────────────────────────────────────

class WorkPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "list":
            return WorkPlanListSerializer
        return WorkPlanSerializer

    def get_queryset(self):
        user = self.request.user
        qs = WorkPlan.objects.select_related(
            "department", "created_by"
        ).prefetch_related("items")

        if can_view_all(user):
            pass  # hamma rejayi ko'radi
        else:
            dept_ids = get_user_dept_ids(user)
            qs = qs.filter(department_id__in=dept_ids)

        year = self.request.query_params.get("year")
        if year:
            qs = qs.filter(year=year)
        dept = self.request.query_params.get("department")
        if dept:
            qs = qs.filter(department_id=dept)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ── Tasdiqlash / Rad etish ────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        if not can_view_all(request.user):
            return Response({"detail": "Ruxsat yo'q"}, status=403)
        plan = self.get_object()
        from django.utils import timezone as tz
        plan.status = WorkPlan.Status.APPROVED
        plan.approved_by = request.user
        plan.approved_at = tz.now()
        plan.reject_reason = ""
        plan.save(update_fields=["status", "approved_by", "approved_at", "reject_reason"])
        return Response(WorkPlanSerializer(plan).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        if not can_view_all(request.user):
            return Response({"detail": "Ruxsat yo'q"}, status=403)
        plan = self.get_object()
        reason = request.data.get("reason", "").strip()
        plan.status = WorkPlan.Status.REJECTED
        plan.approved_by = None
        plan.approved_at = None
        plan.reject_reason = reason
        plan.save(update_fields=["status", "approved_by", "approved_at", "reject_reason"])
        return Response(WorkPlanSerializer(plan).data)

    # ── Bandlar CRUD ──────────────────────────────────────────────
    @action(detail=True, methods=["get", "post"], url_path="items")
    def items(self, request, pk=None):
        plan = self.get_object()

        if request.method == "GET":
            return Response(WorkPlanItemSerializer(plan.items.all(), many=True).data)

        # Tasdiqlangan rejaga band qo'shib bo'lmaydi
        if plan.is_approved:
            return Response({"detail": "Tasdiqlangan rejani o'zgartirish mumkin emas"}, status=403)

        data = request.data.copy()
        data["work_plan"] = plan.id
        if not data.get("order_number"):
            last = plan.items.order_by("-order_number").first()
            data["order_number"] = (last.order_number + 1) if last else 1

        serializer = WorkPlanItemSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(work_plan=plan)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put", "patch", "delete"], url_path=r"items/(?P<item_id>\d+)")
    def item_detail(self, request, pk=None, item_id=None):
        plan = self.get_object()

        if plan.is_approved:
            return Response({"detail": "Tasdiqlangan rejani o'zgartirish mumkin emas"}, status=403)

        from django.shortcuts import get_object_or_404
        item = get_object_or_404(WorkPlanItem, id=item_id, work_plan=plan)

        if request.method == "DELETE":
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = WorkPlanItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # ── Exceldan import ───────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="import-excel",
            parser_classes=[MultiPartParser, FormParser])
    def import_excel(self, request, pk=None):
        plan = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl talab qilinadi"}, status=400)

        try:
            import openpyxl
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))
        except Exception as e:
            return Response({"detail": f"Faylni o'qishda xato: {e}"}, status=400)

        MONTHS = {
            "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4,
            "may": 5, "iyun": 6, "iyul": 7, "avgust": 8,
            "sentabr": 9, "oktabr": 10, "noyabr": 11, "dekabr": 12,
        }

        created = []
        offset = plan.items.count()
        for i, row in enumerate(rows, start=1):
            if not row or not row[0]:
                continue
            content     = str(row[0]).strip() if row[0] else ""
            period_raw  = str(row[1]).strip().lower() if len(row) > 1 and row[1] else ""

            if not content:
                continue

            period_type    = WorkPlanItem.PeriodType.YEARLY
            deadline_month = None

            if period_raw in MONTHS:
                period_type    = WorkPlanItem.PeriodType.MONTHLY
                deadline_month = MONTHS[period_raw]
            elif any(str(m) in period_raw for m in range(1, 13)):
                for m in range(1, 13):
                    if str(m) in period_raw:
                        period_type    = WorkPlanItem.PeriodType.MONTHLY
                        deadline_month = m
                        break

            item = WorkPlanItem.objects.create(
                work_plan=plan,
                order_number=offset + i,
                content=content,
                period_type=period_type,
                deadline_month=deadline_month,
            )
            created.append(item)

        return Response(
            WorkPlanItemSerializer(plan.items.all(), many=True).data,
            status=status.HTTP_201_CREATED,
        )


# ── DailyReport ───────────────────────────────────────────────────────────────

class DailyReportViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return DailyReportCreateSerializer
        return DailyReportSerializer

    def get_queryset(self):
        user = self.request.user
        qs = DailyReport.objects.select_related(
            "author", "department", "work_plan_item"
        ).prefetch_related("images")

        if can_view_all(user):
            pass
        else:
            dept_ids = get_user_dept_ids(user)
            qs = qs.filter(department_id__in=dept_ids)

        # Filterlar
        dept = self.request.query_params.get("department")
        if dept:
            qs = qs.filter(department_id=dept)
        date = self.request.query_params.get("date")
        if date:
            qs = qs.filter(date=date)
        author = self.request.query_params.get("author")
        if author:
            qs = qs.filter(author_id=author)
        # Sana oralig'i
        date_from = self.request.query_params.get("date_from")
        date_to   = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        return qs

    def perform_create(self, serializer):
        dept = serializer.validated_data.get("department")
        if dept:
            current_year = timezone.localdate().year
            approved = WorkPlan.objects.filter(
                department=dept,
                year=current_year,
                status=WorkPlan.Status.APPROVED,
            ).exists()
            if not approved:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    "Bo'limning yillik ish rejasi tasdiqlanmagan. Hisobot kiritish mumkin emas."
                )
        serializer.save(author=self.request.user)

    # ── Rasm qo'shish ─────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="images",
            parser_classes=[MultiPartParser, FormParser])
    def add_image(self, request, pk=None):
        report = self.get_object()
        images = request.FILES.getlist("images")
        if not images:
            return Response({"detail": "Rasm talab qilinadi"}, status=400)
        created = []
        for img in images:
            obj = DailyReportImage.objects.create(report=report, image=img)
            created.append(obj)
        return Response(DailyReportImageSerializer(created, many=True).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        report = self.get_object()
        from django.shortcuts import get_object_or_404
        img = get_object_or_404(DailyReportImage, id=image_id, report=report)
        img.image.delete(save=False)
        img.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── WeeklyReport ──────────────────────────────────────────────────────────────

def get_or_create_weekly_report(department):
    """Joriy hafta uchun haftalik hisobotni topadi yoki yaratadi."""
    today = timezone.localdate()
    # ISO: dushanba=0 ... yakshanba=6
    week_start = today - datetime.timedelta(days=today.weekday())
    week_end   = week_start + datetime.timedelta(days=6)
    year, week_number, _ = today.isocalendar()

    report, created = WeeklyReport.objects.get_or_create(
        department=department,
        year=year,
        week_number=week_number,
        defaults={
            "week_start": week_start,
            "week_end":   week_end,
        },
    )
    return report, created


class WeeklyReportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "list":
            return WeeklyReportListSerializer
        return WeeklyReportSerializer

    def get_queryset(self):
        user = self.request.user
        qs = WeeklyReport.objects.select_related("department").prefetch_related("extras__images")

        if can_view_all(user):
            pass
        else:
            dept_ids = get_user_dept_ids(user)
            qs = qs.filter(department_id__in=dept_ids)

        dept = self.request.query_params.get("department")
        if dept:
            qs = qs.filter(department_id=dept)
        year = self.request.query_params.get("year")
        if year:
            qs = qs.filter(year=year)

        return qs

    # ── Joriy hafta (avtomatik yaratish) ─────────────────────────
    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        user = request.user
        dept_ids = get_user_dept_ids(user)
        if not dept_ids:
            return Response({"detail": "Siz hech qaysi bo'limga biriktirilmagansiz"}, status=400)

        dept_id = request.query_params.get("department") or dept_ids[0]

        from apps.organizations.models import Department
        from django.shortcuts import get_object_or_404
        dept = get_object_or_404(Department, id=dept_id)

        report, created = get_or_create_weekly_report(dept)
        data = WeeklyReportSerializer(report).data
        data["just_created"] = created
        return Response(data)

    # ── Qo'shimcha band qo'shish ──────────────────────────────────
    @action(detail=True, methods=["post"], url_path="extras",
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def add_extra(self, request, pk=None):
        report = self.get_object()
        content = request.data.get("content", "").strip()
        if not content:
            return Response({"detail": "Mazmun kiritilishi shart"}, status=400)

        is_outside = request.data.get("is_outside_plan", "false")
        is_outside = is_outside in (True, "true", "True", "1")

        work_plan_item = None
        item_id = request.data.get("work_plan_item")
        if item_id and not is_outside:
            from django.shortcuts import get_object_or_404
            work_plan_item = get_object_or_404(WorkPlanItem, id=item_id)

        extra = WeeklyReportExtra.objects.create(
            weekly_report=report,
            content=content,
            work_plan_item=work_plan_item,
            is_outside_plan=is_outside,
            created_by=request.user,
        )

        for img in request.FILES.getlist("images"):
            WeeklyReportExtraImage.objects.create(extra=extra, image=img)

        return Response(WeeklyReportExtraSerializer(extra).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"extras/(?P<extra_id>\d+)")
    def delete_extra(self, request, pk=None, extra_id=None):
        report = self.get_object()
        from django.shortcuts import get_object_or_404
        extra = get_object_or_404(WeeklyReportExtra, id=extra_id, weekly_report=report)
        extra.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path=r"extras/(?P<extra_id>\d+)/images",
            parser_classes=[MultiPartParser, FormParser])
    def add_extra_image(self, request, pk=None, extra_id=None):
        report = self.get_object()
        from django.shortcuts import get_object_or_404
        extra = get_object_or_404(WeeklyReportExtra, id=extra_id, weekly_report=report)
        created = []
        for img in request.FILES.getlist("images"):
            obj = WeeklyReportExtraImage.objects.create(extra=extra, image=img)
            created.append(obj)
        return Response(WeeklyReportExtraImageSerializer(created, many=True).data,
                        status=status.HTTP_201_CREATED)
