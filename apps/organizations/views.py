from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Organization, Department, Chair
from .serializers import OrganizationSerializer, DepartmentSerializer, ChairSerializer
from apps.accounts.permissions import IsSuperAdmin


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.prefetch_related("branches", "departments").order_by(
        "org_type", "name"
    )
    serializer_class = OrganizationSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["org_type", "is_active", "parent"]
    search_fields = ["name", "short_name"]

    @action(detail=True, methods=["get"])
    def departments(self, request, pk=None):
        org = self.get_object()
        depts = org.departments.filter(is_active=True).prefetch_related("chairs")
        return Response(DepartmentSerializer(depts, many=True).data)

    @action(detail=True, methods=["get"])
    def branches(self, request, pk=None):
        org = self.get_object()
        branches = org.branches.filter(is_active=True)
        return Response(OrganizationSerializer(branches, many=True).data)


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related("organization").prefetch_related(
        "chairs"
    ).order_by("organization", "name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["organization", "dept_type", "can_create_tasks", "is_active"]
    search_fields = ["name"]

    @action(detail=True, methods=["get"])
    def chairs(self, request, pk=None):
        dept = self.get_object()
        chairs = dept.chairs.filter(is_active=True)
        return Response(ChairSerializer(chairs, many=True).data)


class ChairViewSet(viewsets.ModelViewSet):
    queryset = Chair.objects.select_related("department__organization").order_by(
        "department", "name"
    )
    serializer_class = ChairSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["department", "is_active"]
    search_fields = ["name"]


# Non-admin read views
class PublicOrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.filter(is_active=True).order_by("org_type", "name")
    serializer_class = OrganizationSerializer
    filterset_fields = ["org_type", "parent"]


class PublicDepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.filter(is_active=True).select_related("organization")
    serializer_class = DepartmentSerializer
    filterset_fields = ["organization", "dept_type"]
