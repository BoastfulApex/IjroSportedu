from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from django.core.cache import cache

from apps.tasks.models import Task
from apps.organizations.models import Organization
from apps.accounts.permissions import CanViewAllReports


class OverviewReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewAllReports]

    def get(self, request):
        cache_key = "report_overview"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        now = timezone.now()
        total = Task.objects.count()
        by_status = dict(
            Task.objects.values_list("status").annotate(count=Count("id"))
        )
        by_priority = dict(
            Task.objects.values_list("priority").annotate(count=Count("id"))
        )
        overdue = Task.objects.filter(
            deadline__lt=now,
            status__in=[
                Task.Status.CREATED, Task.Status.ASSIGNED,
                Task.Status.ACCEPTED, Task.Status.IN_PROGRESS,
                Task.Status.SUBMITTED, Task.Status.REVIEWING,
            ]
        ).count()

        data = {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "overdue": overdue,
            "closed_today": Task.objects.filter(
                status=Task.Status.CLOSED,
                updated_at__date=now.date(),
            ).count(),
        }
        cache.set(cache_key, data, timeout=300)
        return Response(data)


class ByOrganizationReportView(APIView):
    permission_classes = [IsAuthenticated, CanViewAllReports]

    def get(self, request):
        orgs = Organization.objects.filter(is_active=True).prefetch_related("received_tasks")
        data = []
        for org in orgs:
            tasks = org.received_tasks
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
        return Response(list(qs))


class OverdueTasksView(APIView):
    permission_classes = [IsAuthenticated, CanViewAllReports]

    def get(self, request):
        now = timezone.now()
        tasks = Task.objects.filter(
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
