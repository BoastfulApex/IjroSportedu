from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Task, TaskAssignee, TaskAttachment, TaskComment, TaskHistory
from .serializers import (
    TaskListSerializer, TaskDetailSerializer, TaskCreateSerializer,
    TaskStatusUpdateSerializer, TaskAssigneeSerializer,
    TaskAttachmentSerializer, TaskCommentSerializer, TaskHistorySerializer,
)
from apps.accounts.permissions import IsTaskController, CanCreateTask, IsTaskRelated
from apps.accounts.models import User


class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "priority", "target_organization", "target_department", "is_overdue"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "deadline", "priority", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related(
            "creator", "creating_department__organization",
            "target_organization", "target_department",
        ).prefetch_related("assignees__user")

        if user.is_super_admin() or user.is_task_controller():
            return qs

        # Institute leader can see all tasks
        if user.is_institute_leader():
            return qs

        # Others see tasks for their org or assigned to them
        user_org_ids = list(
            user.role_assignments.filter(is_active=True)
            .exclude(organization=None)
            .values_list("organization_id", flat=True)
        )
        return qs.filter(
            Q(assignees__user=user)
            | Q(creator=user)
            | Q(target_organization__in=user_org_ids)
        ).distinct()

    def get_serializer_class(self):
        if self.action in ["list"]:
            return TaskListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return TaskCreateSerializer
        return TaskDetailSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.is_super_admin() or user.is_task_controller()):
            from apps.accounts.models import UserRoleAssignment
            assignment = UserRoleAssignment.objects.filter(
                user=user, is_active=True, department__can_create_tasks=True
            ).select_related("department").first()
            if not assignment:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Sizda topshiriq yaratish huquqi yo'q")
            dept = assignment.department
        else:
            from apps.accounts.models import UserRoleAssignment
            assignment = UserRoleAssignment.objects.filter(
                user=user, is_active=True, department__isnull=False
            ).select_related("department").first()
            dept = assignment.department if assignment else None

        task = serializer.save(creator=user, creating_department=dept)
        task._actor = user

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), CanCreateTask()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        task = self.get_object()
        serializer = TaskStatusUpdateSerializer(
            data=request.data, context={"task": task, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        comment_text = serializer.validated_data.get("comment", "")

        old_status = task.status
        task.status = new_status
        task._actor = request.user
        task.save()

        if comment_text:
            TaskComment.objects.create(task=task, author=request.user, content=comment_text)

        # Trigger notification
        from apps.notifications.tasks import send_status_change_notification
        send_status_change_notification.delay(task.id, old_status, new_status)

        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post", "get"], url_path="assignees")
    def assignees(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(TaskAssigneeSerializer(task.assignees.all(), many=True).data)

        user_id = request.data.get("user")
        user = get_object_or_404(User, id=user_id, is_active=True)
        assignee, created = TaskAssignee.objects.get_or_create(
            task=task, user=user,
            defaults={"assigned_by": request.user},
        )
        if not created:
            return Response({"detail": "Ijrochi allaqachon biriktirilgan"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TaskAssigneeSerializer(assignee).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"assignees/(?P<user_id>\d+)")
    def remove_assignee(self, request, pk=None, user_id=None):
        task = self.get_object()
        assignee = get_object_or_404(TaskAssignee, task=task, user_id=user_id)
        TaskHistory.objects.create(
            task=task, actor=request.user,
            action="Ijrochi olib tashlandi",
            old_value=assignee.user.full_name,
        )
        assignee.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post", "get"], url_path="attachments",
            parser_classes=[MultiPartParser, FormParser])
    def attachments(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(
                TaskAttachmentSerializer(
                    task.attachments.all(), many=True, context={"request": request}
                ).data
            )
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl yuborilmadi"}, status=status.HTTP_400_BAD_REQUEST)

        from django.conf import settings
        if file.size > settings.MAX_UPLOAD_SIZE:
            return Response({"detail": "Fayl hajmi 10MB dan oshmasligi kerak"}, status=400)

        attachment = TaskAttachment.objects.create(
            task=task,
            file=file,
            filename=file.name,
            file_size=file.size,
            uploaded_by=request.user,
        )
        TaskHistory.objects.create(
            task=task, actor=request.user,
            action="Fayl yuklandi", new_value=file.name,
        )
        return Response(
            TaskAttachmentSerializer(attachment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<att_id>\d+)")
    def delete_attachment(self, request, pk=None, att_id=None):
        task = self.get_object()
        att = get_object_or_404(TaskAttachment, id=att_id, task=task)
        att.file.delete(save=False)
        att.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(
                TaskCommentSerializer(task.comments.select_related("author"), many=True).data
            )
        serializer = TaskCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(task=task, author=request.user)

        from apps.notifications.tasks import send_comment_notification
        send_comment_notification.delay(task.id, comment.id, request.user.id)

        return Response(TaskCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put", "delete"], url_path=r"comments/(?P<comment_id>\d+)")
    def comment_detail(self, request, pk=None, comment_id=None):
        task = self.get_object()
        comment = get_object_or_404(TaskComment, id=comment_id, task=task)

        if request.method == "DELETE":
            if comment.author != request.user and not request.user.is_super_admin():
                return Response({"detail": "Ruxsat yo'q"}, status=status.HTTP_403_FORBIDDEN)
            comment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if comment.author != request.user:
            return Response({"detail": "Faqat o'z izohingizni tahrirlash mumkin"}, status=403)
        serializer = TaskCommentSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(is_edited=True)
        return Response(TaskCommentSerializer(comment).data)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        task = self.get_object()
        history = task.history.select_related("actor").order_by("-timestamp")
        return Response(TaskHistorySerializer(history, many=True).data)
