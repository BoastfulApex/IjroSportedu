from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from django.core.cache import cache

from apps.tasks.models import Task
from apps.organizations.models import Organization
from apps.accounts.permissions import CanViewAllReports


def get_task_qs_for_user(user):
    """Foydalanuvchi ko'ra oladigan tasklarni qaytaradi."""
    org_ids = user.get_report_org_ids()
    if org_ids is None:
        return Task.objects.all()
    if not org_ids:
        return Task.objects.none()
    return Task.objects.filter(target_organization__in=org_ids)


class OverviewReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewAllReports]

    def get(self, request):
        user = request.user
        org_ids = user.get_report_org_ids()

        # Super admin / task controller / institute leader uchun cache
        if org_ids is None:
            cached = cache.get("report_overview")
            if cached:
                return Response(cached)

        qs = get_task_qs_for_user(user)
        now = timezone.now()

        by_status = dict(qs.values_list("status").annotate(count=Count("id")))
        by_priority = dict(qs.values_list("priority").annotate(count=Count("id")))

        overdue_qs = qs.filter(
            deadline__lt=now,
            status__in=[
                Task.Status.CREATED, Task.Status.ASSIGNED,
                Task.Status.ACCEPTED, Task.Status.IN_PROGRESS,
                Task.Status.SUBMITTED, Task.Status.REVIEWING,
            ]
        )
        active_qs = qs.filter(
            status__in=[Task.Status.IN_PROGRESS, Task.Status.ACCEPTED]
        )
        closed_qs = qs.filter(status=Task.Status.CLOSED)

        def by_type(queryset):
            return dict(queryset.values_list("task_type").annotate(c=Count("id")))

        data = {
            "total":         qs.count(),
            "by_status":     by_status,
            "by_priority":   by_priority,
            "overdue":       overdue_qs.count(),
            "closed_today":  closed_qs.filter(updated_at__date=now.date()).count(),
            # Tur bo'yicha breakdownlar
            "total_by_type":   by_type(qs),
            "active_by_type":  by_type(active_qs),
            "closed_by_type":  by_type(closed_qs),
            "overdue_by_type": by_type(overdue_qs),
        }

        if org_ids is None:
            cache.set("report_overview", data, timeout=300)
        return Response(data)


class ByOrganizationReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewAllReports]

    def get(self, request):
        user = request.user
        org_ids = user.get_report_org_ids()

        orgs = Organization.objects.filter(is_active=True)
        if org_ids is not None:
            orgs = orgs.filter(id__in=org_ids)

        data = []
        for org in orgs.prefetch_related("received_tasks"):
            tasks = org.received_tasks.all()
            data.append({
                "organization_id": org.id,
                "organization_name": org.name,
                "org_type": org.org_type,
                "total": tasks.count(),
                "by_status": dict(tasks.values_list("status").annotate(c=Count("id"))),
                "overdue": tasks.filter(is_overdue=True).count(),
            })
        return Response(data)


class ByDepartmentReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewAllReports]

    def get(self, request):
        user = request.user
        org_ids = user.get_report_org_ids()
        org_id = request.query_params.get("organization")

        qs = Task.objects.values(
            "target_department__id",
            "target_department__name",
            "target_department__organization__name",
        ).annotate(
            total=Count("id"),
            overdue=Count("id", filter=Q(is_overdue=True)),
        )

        if org_id:
            qs = qs.filter(target_organization_id=org_id)
        elif org_ids is not None:
            qs = qs.filter(target_organization__in=org_ids)

        return Response(list(qs))


class OverdueTasksView(APIView):
    permission_classes = [IsAuthenticated, CanViewAllReports]

    def get(self, request):
        now = timezone.now()
        tasks = get_task_qs_for_user(request.user).filter(
            deadline__lt=now,
            status__in=[
                Task.Status.CREATED, Task.Status.ASSIGNED,
                Task.Status.ACCEPTED, Task.Status.IN_PROGRESS,
                Task.Status.SUBMITTED, Task.Status.REVIEWING,
            ]
        ).select_related(
            "creator", "target_organization", "target_department", "creating_department"
        ).prefetch_related("assignees__user").order_by("deadline")

        from apps.tasks.serializers import TaskListSerializer
        return Response(TaskListSerializer(tasks, many=True).data)


class MyTasksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        tasks = Task.objects.filter(
            Q(assignees__user=user) | Q(creator=user)
        ).distinct().select_related(
            "creator", "target_organization", "target_department"
        ).order_by("-created_at")

        from apps.tasks.serializers import TaskListSerializer
        return Response(TaskListSerializer(tasks, many=True).data)
