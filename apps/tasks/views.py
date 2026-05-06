from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Task, TaskOrganizationTarget, TaskAssignee, TaskAttachment, TaskComment, TaskHistory, Meeting, MeetingAgendaItem
from .serializers import (
    TaskListSerializer, TaskDetailSerializer, TaskCreateSerializer,
    TaskStatusUpdateSerializer, TaskAssigneeSerializer,
    TaskAttachmentSerializer, TaskCommentSerializer, TaskHistorySerializer,
    MeetingSerializer, MeetingListSerializer, MeetingAgendaItemSerializer,
)
from apps.accounts.permissions import IsTaskController, CanCreateTask, IsTaskRelated
from apps.accounts.models import User


class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "priority", "task_type", "target_organization", "target_department", "is_overdue"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "deadline", "priority", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related(
            "creator", "creating_department__organization",
            "target_organization", "target_department",
        ).prefetch_related(
            "assignees__user",
            "assignees__organization",
            "assignees__department",
            "assignees__chair",
            "org_targets__organization",
            "org_targets__department",
            "org_targets__chair",
        )

        # ?my_tasks=true — faqat o'zi ijrochi sifatida biriktirilgan topshiriqlar
        if self.request.query_params.get("my_tasks") == "true":
            return qs.filter(assignees__user=user).distinct()

        if user.is_super_admin() or user.is_task_controller():
            return qs

        if user.is_institute_leader():
            return qs

        active_roles = user.role_assignments.filter(is_active=True)
        user_org_ids = list(
            active_roles.exclude(organization=None)
            .values_list("organization_id", flat=True)
        )
        user_dept_ids = list(
            active_roles.exclude(department=None)
            .values_list("department_id", flat=True)
        )
        return qs.filter(
            Q(assignees__user=user)
            | Q(creator=user)
            | Q(target_organization__in=user_org_ids)
            | Q(target_department__in=user_dept_ids)
            # Ko'p manzilli topshiriqlar: org_targets orqali ham ko'ra oladi
            | Q(org_targets__organization__in=user_org_ids)
            | Q(org_targets__department__in=user_dept_ids)
        ).distinct()

    def get_serializer_class(self):
        if self.action in ["list"]:
            return TaskListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return TaskCreateSerializer
        return TaskDetailSerializer

    def perform_create(self, serializer):
        from apps.accounts.models import UserRoleAssignment
        from apps.organizations.models import Organization, Department
        from django.db.models import Q as DQ
        user = self.request.user

        if user.is_super_admin() or user.is_task_controller():
            assignment = UserRoleAssignment.objects.filter(
                user=user, is_active=True, department__isnull=False
            ).select_related("department").first()
            dept = assignment.department if assignment else None
        else:
            assignment = UserRoleAssignment.objects.filter(
                user=user, is_active=True
            ).filter(
                DQ(department__can_create_tasks=True)
                | DQ(department__dept_type="TASK_CONTROL")
            ).select_related("department").first()
            if not assignment:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Sizda topshiriq yaratish huquqi yo'q")
            dept = assignment.department

        # targets — validated_data dan olib tashlab, qo'lda ishlaymiz
        targets_data = serializer.validated_data.pop("targets", [])
        first = targets_data[0] if targets_data else {}

        task = serializer.save(
            creator=user,
            creating_department=dept,
            target_organization_id=first.get("organization"),
            target_department_id=first.get("department"),
        )
        task._actor = user

        # Har bir manzil uchun TaskOrganizationTarget yaratamiz
        import logging
        logger = logging.getLogger(__name__)
        for t in targets_data:
            try:
                TaskOrganizationTarget.objects.create(
                    task=task,
                    organization_id=t.get("organization"),
                    department_id=t.get("department"),
                    chair_id=t.get("chair"),
                )
            except Exception as e:
                logger.error(f"TaskOrganizationTarget yaratishda xatolik: {e}, data={t}")

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
        try:
            from apps.notifications.tasks import send_status_change_notification
            send_status_change_notification.delay(task.id, old_status, new_status)
        except Exception:
            pass

        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post", "get"], url_path="assignees")
    def assignees(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            return Response(TaskAssigneeSerializer(task.assignees.select_related(
                "user", "organization", "department"
            ).all(), many=True).data)

        user_id    = request.data.get("user")
        is_primary = bool(request.data.get("is_primary", False))
        is_leader  = bool(request.data.get("is_leader",  False))
        org_id     = request.data.get("organization")
        dept_id    = request.data.get("department")
        chair_id   = request.data.get("chair")

        user = get_object_or_404(User, id=user_id, is_active=True)

        # Allaqachon biriktirilganini tekshir
        if task.assignees.filter(user=user).exists():
            return Response({"detail": "Ijrochi allaqachon biriktirilgan"}, status=status.HTTP_400_BAD_REQUEST)

        # Faqat bitta asosiy ijrochi bo'lishi mumkin — avvalgi primary'ni tozala
        if is_primary:
            task.assignees.filter(is_primary=True).update(is_primary=False)

        assignee = TaskAssignee.objects.create(
            task=task,
            user=user,
            assigned_by=request.user,
            organization_id=org_id,
            department_id=dept_id,
            chair_id=chair_id,
            is_primary=is_primary,
            is_leader=is_leader,
        )
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

        attachment_type = request.data.get("attachment_type", TaskAttachment.AttachmentType.TASK_FILE)
        if attachment_type not in TaskAttachment.AttachmentType.values:
            attachment_type = TaskAttachment.AttachmentType.TASK_FILE

        attachment = TaskAttachment.objects.create(
            task=task,
            file=file,
            filename=file.name,
            file_size=file.size,
            attachment_type=attachment_type,
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

        try:
            from apps.notifications.tasks import send_comment_notification
            send_comment_notification.delay(task.id, comment.id, request.user.id)
        except Exception:
            pass

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


# ── Majlis ViewSet ──────────────────────────────────────────────────────────

class MeetingViewSet(viewsets.ModelViewSet):
    """
    Majlis (Rektorat / Ilmiy kengash) topshiriqlari.
    Excel yuklab, har bir band uchun ijrochi va muddat belgilab, tasdiqlanganda
    haqiqiy Task ob'ektlari yaratiladi.
    """
    permission_classes = [IsAuthenticated, IsTaskController]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Meeting.objects.prefetch_related("items__task").select_related("created_by")

    def get_serializer_class(self):
        if self.action == "list":
            return MeetingListSerializer
        return MeetingSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ── Excel yuklash ──────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="upload",
            parser_classes=[MultiPartParser, FormParser])
    def upload_excel(self, request, pk=None):
        meeting = self.get_object()
        if meeting.is_confirmed:
            return Response({"detail": "Majlis tasdiqlangan, o'zgartirish mumkin emas"}, status=400)

        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl yuborilmadi"}, status=400)

        # Fayl kengaytmasini tekshir
        name = file.name.lower()
        if not (name.endswith(".xlsx") or name.endswith(".xls")):
            return Response({"detail": "Faqat Excel fayl (.xlsx, .xls) qabul qilinadi"}, status=400)

        try:
            import openpyxl
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as e:
            return Response({"detail": f"Excel faylni o'qib bo'lmadi: {e}"}, status=400)

        # Sarlavha qatorini o'tkazib yuborish (1-qator) va ma'lumot qatorlarini olish
        data_rows = rows[1:] if len(rows) > 1 else rows

        items_data = []
        for row in data_rows:
            if not row or len(row) < 2:
                continue
            band_num = row[0]
            content  = row[1]
            if band_num is None or content is None:
                continue
            try:
                band_num = int(band_num)
            except (ValueError, TypeError):
                continue
            content = str(content).strip()
            if content:
                items_data.append({"band_number": band_num, "content": content})

        if not items_data:
            return Response({"detail": "Excel faylda ma'lumot topilmadi"}, status=400)

        # Avvalgi bandlarni o'chirib, yangisini yozamiz
        meeting.items.filter(task__isnull=True).delete()

        created = []
        for item in items_data:
            obj, _ = MeetingAgendaItem.objects.get_or_create(
                meeting=meeting,
                band_number=item["band_number"],
                defaults={"content": item["content"]},
            )
            created.append(obj)

        return Response(MeetingAgendaItemSerializer(created, many=True).data)

    # ── Tasdiqlash: har bir band uchun task yaratish ───────────────
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """
        Body:
        {
          "items": [
            {
              "id": 1,
              "deadline": "2026-06-01T17:00",
              "priority": "HIGH",
              "target_organization": 3,
              "target_department": null,
              "assignees": [
                {"user": 5, "is_primary": true, "organization": 3, "department": 2}
              ]
            },
            ...
          ]
        }
        """
        meeting = self.get_object()
        if meeting.is_confirmed:
            return Response({"detail": "Majlis allaqachon tasdiqlangan"}, status=400)

        items_payload = request.data.get("items", [])
        if not items_payload:
            return Response({"detail": "Bandlar ro'yxati bo'sh"}, status=400)

        from apps.accounts.models import UserRoleAssignment
        from apps.organizations.models import Organization, Department
        from django.utils import timezone as tz

        # Creator department ni aniqlash
        user = request.user
        if user.is_super_admin() or user.is_task_controller():
            creating_dept = None
        else:
            assignment = UserRoleAssignment.objects.filter(
                user=user, is_active=True
            ).filter(
                Q(department__can_create_tasks=True) | Q(department__dept_type="TASK_CONTROL")
            ).select_related("department").first()
            creating_dept = assignment.department if assignment else None

        errors = []
        created_tasks = []

        for payload in items_payload:
            item_id   = payload.get("id")
            deadline  = payload.get("deadline")
            priority  = payload.get("priority", Task.Priority.MEDIUM)
            target_org_id  = payload.get("target_organization")
            target_dept_id = payload.get("target_department")
            assignees_data = payload.get("assignees", [])

            try:
                item = MeetingAgendaItem.objects.get(id=item_id, meeting=meeting)
            except MeetingAgendaItem.DoesNotExist:
                errors.append(f"Band #{item_id} topilmadi")
                continue

            if item.task:
                continue  # Allaqachon yaratilgan

            if not target_org_id:
                errors.append(f"Band #{item.band_number}: tashkilot tanlanmagan")
                continue

            if not assignees_data:
                errors.append(f"Band #{item.band_number}: ijrochi biriktirilmagan")
                continue

            try:
                target_org = Organization.objects.get(id=target_org_id)
            except Organization.DoesNotExist:
                errors.append(f"Band #{item.band_number}: tashkilot topilmadi")
                continue

            # Deadline parse
            parsed_deadline = None
            if deadline:
                try:
                    from django.utils.dateparse import parse_datetime
                    parsed_deadline = parse_datetime(deadline)
                    if parsed_deadline and tz.is_naive(parsed_deadline):
                        parsed_deadline = tz.make_aware(parsed_deadline)
                except Exception:
                    pass

            # Task type majlis turidan olinadi
            task_type_map = {
                Meeting.MeetingType.REKTORAT: Task.TaskType.REKTORAT,
                Meeting.MeetingType.ILMIY:    Task.TaskType.ILMIY,
            }
            task_type = task_type_map.get(meeting.meeting_type, Task.TaskType.FUNKSIONAL)

            # Task yaratish
            task = Task.objects.create(
                title=f"{meeting.name} — {item.band_number}-band: {item.content[:200]}",
                description=item.content,
                priority=priority,
                task_type=task_type,
                creator=user,
                creating_department=creating_dept,
                target_organization=target_org,
                target_department_id=target_dept_id,
                deadline=parsed_deadline,
            )

            # Ijrochilar
            primary_set = False
            for a in assignees_data:
                a_user_id  = a.get("user")
                a_is_prim  = bool(a.get("is_primary", False))
                a_is_lead  = bool(a.get("is_leader",  False))
                a_org_id   = a.get("organization")
                a_dept_id  = a.get("department")

                if not a_user_id:
                    continue

                try:
                    a_user = User.objects.get(id=a_user_id)
                except User.DoesNotExist:
                    continue

                if a_is_prim and primary_set:
                    a_is_prim = False  # faqat bitta primary

                TaskAssignee.objects.create(
                    task=task,
                    user=a_user,
                    assigned_by=user,
                    organization_id=a_org_id or target_org_id,
                    department_id=a_dept_id,
                    is_primary=a_is_prim,
                    is_leader=a_is_lead,
                )
                if a_is_prim:
                    primary_set = True

            # org_targets
            TaskOrganizationTarget.objects.create(
                task=task,
                organization=target_org,
                department_id=target_dept_id,
            )

            # Band bilan bog'laymiz
            item.task = task
            item.save(update_fields=["task"])
            created_tasks.append(task.id)

        # Agar barcha bandlar yaratilgan bo'lsa — confirmed
        total    = meeting.items.count()
        done     = meeting.items.filter(task__isnull=False).count()
        if done == total and total > 0:
            meeting.is_confirmed = True
            meeting.save(update_fields=["is_confirmed"])

        return Response({
            "created": len(created_tasks),
            "errors":  errors,
            "is_confirmed": meeting.is_confirmed,
        })
