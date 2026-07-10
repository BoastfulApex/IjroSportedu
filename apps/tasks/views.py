from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Case, When, IntegerField, F
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Task, TaskOrganizationTarget, TaskAssignee, TaskAttachment, TaskComment, TaskHistory, Meeting, MeetingAgendaItem, RecurringMeetingItem
from .serializers import (
    TaskListSerializer, TaskDetailSerializer, TaskCreateSerializer,
    TaskStatusUpdateSerializer, TaskAssigneeSerializer,
    TaskAttachmentSerializer, TaskCommentSerializer, TaskHistorySerializer,
    MeetingSerializer, MeetingListSerializer, MeetingAgendaItemSerializer,
    RecurringMeetingItemSerializer,
)


def get_next_saturday_15():
    """Bu hafta yoki keyingi shanba kuni soat 15:00 (aware datetime)."""
    from datetime import timedelta
    from django.utils import timezone as tz
    now = tz.now()
    # weekday(): 0=Dushanba … 5=Shanba, 6=Yakshanba
    days_until_sat = (5 - now.weekday()) % 7
    if days_until_sat == 0:
        days_until_sat = 7  # agar bugun shanba bo'lsa → keyingi shanba
    saturday = (now + timedelta(days=days_until_sat)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    return saturday
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
        from django.db.models import Subquery, OuterRef, CharField
        from apps.orders.models import OrderItem
        user = self.request.user
        qs = Task.objects.select_related(
            "creator", "creating_department__organization",
            "target_organization", "target_department",
            "for_all_order_item__order",
            "order_item__order",
        ).prefetch_related(
            "order_item__order__attachments",
            "assignees__user",
            "assignees__organization",
            "assignees__department",
            "assignees__chair",
            "org_targets__organization",
            "org_targets__department",
            "org_targets__chair",
        ).annotate(
            task_order_type=Subquery(
                OrderItem.objects.filter(task_id=OuterRef("pk"))
                .values("order__order_type")[:1],
                output_field=CharField(),
            )
        )

        # ?deadline_after / ?deadline_before — taqvim uchun sana oralig'i filtri
        deadline_after = self.request.query_params.get("deadline_after")
        deadline_before = self.request.query_params.get("deadline_before")
        if deadline_after:
            qs = qs.filter(deadline__date__gte=deadline_after)
        if deadline_before:
            qs = qs.filter(deadline__date__lte=deadline_before)

        # ?my_tasks=true — o'zi ijrochi YOKI target_department xodimi bo'lgan topshiriqlar
        if self.request.query_params.get("my_tasks") == "true":
            active_roles = user.role_assignments.filter(is_active=True)
            my_dept_ids = list(
                active_roles.exclude(department=None)
                .values_list("department_id", flat=True)
            )
            dept_q = Q(target_department__in=my_dept_ids) if my_dept_ids else Q()
            return qs.filter(Q(assignees__user=user) | dept_q).distinct()

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
        if self.action == "download_attachment":
            return [AllowAny()]
        if self.action == "create":
            return [IsAuthenticated(), CanCreateTask()]
        return [IsAuthenticated()]

    def retrieve(self, request, *args, **kwargs):
        """Task ochilganda, ijrochi bo'lsa OrderItemAcknowledgment.viewed_at ni o'rnat."""
        task = self.get_object()
        # order_info uchun kerakli related objectlarni yuklash
        task = (
            Task.objects
            .select_related(
                "creator", "creating_department", "target_organization", "target_department",
                "order_item__order",
                "for_all_order_item__order",
            )
            .prefetch_related(
                "assignees__user", "assignees__organization", "assignees__department",
                "attachments__uploaded_by",
                "org_targets__organization", "org_targets__department",
                "order_item__order__attachments",
                "for_all_order_item__order__attachments",
            )
            .get(pk=task.pk)
        )
        user = request.user
        if task.assignees.filter(user=user).exists():
            try:
                from apps.orders.models import OrderItem, OrderItemAcknowledgment
                order_item = getattr(task, "order_item", None)
                if order_item:
                    OrderItemAcknowledgment.objects.update_or_create(
                        item=order_item,
                        user=user,
                        defaults={"viewed_at": timezone.now()},
                    )
            except Exception:
                pass
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_super_admin():
            return Response({"detail": "Faqat super admin topshiriqni o'chira oladi."}, status=403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        task = self.get_object()
        serializer = TaskStatusUpdateSerializer(
            data=request.data, context={"task": task, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        comment_text = serializer.validated_data.get("comment", "")

        # Status o'zgartirish uchun ruxsat tekshiruvi:
        # Rasmiy ijrochi YOKI target bo'lim a'zosi bo'lishi kerak
        # (SUBMITTED — alohida tekshiruv pastda)
        active_statuses_for_check = [
            Task.Status.ACCEPTED, Task.Status.IN_PROGRESS, Task.Status.RETURNED
        ]
        if new_status in active_statuses_for_check:
            is_assignee = task.assignees.filter(user=request.user).exists()
            if not is_assignee:
                user_dept_ids = list(
                    request.user.role_assignments.filter(is_active=True)
                    .exclude(department=None)
                    .values_list("department_id", flat=True)
                )
                in_target_dept = (
                    task.target_department_id and
                    task.target_department_id in user_dept_ids
                )
                if not in_target_dept:
                    return Response(
                        {"detail": "Siz bu topshiriqning ijrochisi emassiz"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        # Hisobot topshirish — faqat ASOSIY ijrochi
        if new_status == Task.Status.SUBMITTED:
            is_primary = task.assignees.filter(
                user=request.user, is_primary=True
            ).exists()
            if not is_primary:
                return Response(
                    {"detail": "Hisobot faqat asosiy ijrochi tomonidan topshirilishi mumkin"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        from django.utils import timezone as tz
        old_status = task.status
        task.status = new_status
        if new_status == Task.Status.SUBMITTED and not task.submitted_at:
            task.submitted_at = tz.now()
        task._actor = request.user
        task.save()

        if comment_text:
            TaskComment.objects.create(task=task, author=request.user, content=comment_text)

        # Buyruq bandi bilan bog'liq bo'lsa — acknowledgment yangilash
        if new_status == Task.Status.ACCEPTED:
            try:
                from apps.orders.models import OrderItem, OrderItemAcknowledgment
                order_item = OrderItem.objects.filter(task=task).first()
                if order_item:
                    now = tz.now()
                    OrderItemAcknowledgment.objects.update_or_create(
                        item=order_item,
                        user=request.user,
                        defaults={"viewed_at": now, "accepted_at": now},
                    )
            except Exception:
                pass

        # Trigger notification
        try:
            from apps.notifications.tasks import send_status_change_notification
            send_status_change_notification.delay(task.id, old_status, new_status)
        except Exception:
            pass

        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="accept-malumot")
    def accept_malumot(self, request, pk=None):
        """Ma'lumot uchun qabul qilish — task to'g'ridan CLOSED ga o'tadi."""
        task = self.get_object()
        if not task.is_malumot:
            return Response({"detail": "Bu topshiriq ma'lumot uchun emas"}, status=400)
        if not task.assignees.filter(user=request.user).exists():
            return Response({"detail": "Siz bu topshiriqning ijrochisi emassiz"}, status=403)
        if task.status == Task.Status.CLOSED:
            return Response({"detail": "Topshiriq allaqachon yopilgan"}, status=400)

        from django.utils import timezone as tz
        task.status = Task.Status.CLOSED
        task._actor = request.user
        task.save()

        try:
            from apps.orders.models import OrderItem, OrderItemAcknowledgment
            order_item = OrderItem.objects.filter(task=task).first()
            if order_item:
                now = tz.now()
                OrderItemAcknowledgment.objects.update_or_create(
                    item=order_item,
                    user=request.user,
                    defaults={"viewed_at": now, "accepted_at": now},
                )
        except Exception:
            pass

        return Response(TaskDetailSerializer(task, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="deadline")
    def update_deadline(self, request, pk=None):
        """Topshiriq muddatini o'zgartirish (faqat task yaratuvchi / canManage)."""
        task = self.get_object()
        deadline_str = request.data.get("deadline", "").strip()
        if not deadline_str:
            task.deadline = None
            task._actor = request.user
            task.save(update_fields=["deadline"])
            return Response(TaskDetailSerializer(task, context={"request": request}).data)
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone as tz
        deadline = parse_datetime(deadline_str)
        if not deadline:
            return Response({"detail": "Noto'g'ri sana formati"}, status=400)
        if tz.is_naive(deadline):
            deadline = tz.make_aware(deadline)
        old_val = str(task.deadline) if task.deadline else ""
        task.deadline = deadline
        task._actor = request.user
        task.save(update_fields=["deadline"])
        TaskHistory.objects.create(
            task=task, actor=request.user,
            action="Muddat o'zgartirildi",
            old_value=old_val,
            new_value=str(deadline),
        )
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

        # Ruxsat tekshiruvi:
        # TASK_FILE — faqat admin/task controller yuklashi mumkin
        # REPORT_FILE — faqat topshiriq ijrochisi yuklashi mumkin
        user = request.user
        is_admin = user.is_super_admin() or user.is_task_controller()
        is_assignee = task.assignees.filter(user=user).exists()

        if attachment_type == TaskAttachment.AttachmentType.TASK_FILE and not is_admin:
            return Response(
                {"detail": "Topshiriq faylini faqat topshiriqlar bo'limi yoki admin yuklashi mumkin."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if attachment_type == TaskAttachment.AttachmentType.REPORT_FILE and not (is_assignee or is_admin):
            return Response(
                {"detail": "Hisobot faylini faqat topshiriq ijrochisi yuklashi mumkin."},
                status=status.HTTP_403_FORBIDDEN,
            )

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

    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<att_id>\d+)/download",
            authentication_classes=[], permission_classes=[AllowAny])
    def download_attachment(self, request, pk=None, att_id=None):
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        token = request.query_params.get("token")
        user = None
        if token:
            try:
                auth = JWTAuthentication()
                validated = auth.get_validated_token(token)
                user = auth.get_user(validated)
            except (InvalidToken, TokenError):
                pass
        if not user or not user.is_authenticated:
            return Response({"detail": "Autentifikatsiya talab etiladi"}, status=401)
        task = get_object_or_404(Task, pk=pk)
        att = get_object_or_404(TaskAttachment, id=att_id, task=task)
        from django.http import FileResponse
        import os
        if not att.file or not att.file.name:
            return Response({"detail": "Fayl mavjud emas"}, status=404)
        try:
            file_obj = att.file.open("rb")
        except (FileNotFoundError, OSError):
            return Response({"detail": "Fayl diskda topilmadi"}, status=404)
        filename = att.filename or os.path.basename(att.file.name)
        return FileResponse(file_obj, as_attachment=True, filename=filename)

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
    permission_classes = [IsAuthenticated, CanCreateTask]
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

        # Avvalgi topshiriqsiz bandlarni o'chirib, yangisini yozamiz
        meeting.items.filter(task__isnull=True).delete()

        from django.utils import timezone as tz
        current_year = tz.now().year

        # ── 1. Doimiy bandlarni AVVAL qo'shamiz ───────────────────
        recurring_items = []
        recurring_qs = RecurringMeetingItem.objects.filter(
            meeting_type=meeting.meeting_type,
            valid_year=current_year,
            is_active=True,
        )
        for i, rec in enumerate(recurring_qs, start=1):
            already = MeetingAgendaItem.objects.filter(
                meeting=meeting, recurring_item=rec
            ).first()
            if already:
                recurring_items.append(already)
            else:
                rec_item = MeetingAgendaItem.objects.create(
                    meeting=meeting,
                    band_number=i,
                    content=rec.content,
                    recurring_item=rec,
                )
                recurring_items.append(rec_item)

        # ── 2. Excel bandlarini unga qo'shamiz (offset bilan) ─────
        offset = len(recurring_items)
        excel_items = []
        for item in items_data:
            obj, _ = MeetingAgendaItem.objects.get_or_create(
                meeting=meeting,
                band_number=item["band_number"] + offset,
                defaults={"content": item["content"]},
            )
            excel_items.append(obj)

        # Doimiy bandlar TEPADA, Excel bandlar pastda
        all_items = recurring_items + excel_items
        return Response(MeetingAgendaItemSerializer(all_items, many=True).data)

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
            }
            task_type = task_type_map.get(meeting.meeting_type, Task.TaskType.FUNKSIONAL)

            # Task yaratish
            task = Task.objects.create(
                title=f"{meeting.name} — {item.band_number}-band",
                description=item.content,
                priority=priority,
                task_type=task_type,
                creator=user,
                creating_department=creating_dept,
                target_organization=target_org,
                target_department_id=target_dept_id,
                deadline=parsed_deadline,
                meeting=meeting,
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

    @action(detail=True, methods=["post"], url_path="upload-file",
            parser_classes=[MultiPartParser, FormParser])
    def upload_file(self, request, pk=None):
        """Majlisga umumiy fayl biriktirish."""
        meeting = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl tanlanmagan"}, status=400)
        if meeting.file:
            meeting.file.delete(save=False)
        meeting.file = file
        meeting.save(update_fields=["file"])
        return Response(MeetingSerializer(meeting, context={"request": request}).data)

    @action(detail=True, methods=["delete"], url_path=r"items/(?P<item_id>\d+)")
    def remove_item(self, request, pk=None, item_id=None):
        """Band itemni o'chirish.
        - Doimiy band bo'lsa → faqat bu majlisdan olib tashlanadi (RecurringMeetingItem saqlanadi)
        - Oddiy band bo'lsa → butunlay o'chiriladi
        """
        meeting = self.get_object()
        item = get_object_or_404(MeetingAgendaItem, id=item_id, meeting=meeting)
        if item.task_id:
            return Response(
                {"detail": "Bu band allaqachon topshiriqqa aylangan, o'chirib bo'lmaydi"},
                status=400,
            )
        item.delete()  # recurring_item FK SET_NULL → RecurringMeetingItem saqlanadi
        return Response(status=204)

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>\d+)/set-recurring")
    def set_recurring(self, request, pk=None, item_id=None):
        """Bandni doimiy deb belgilash — RecurringMeetingItem yaratiladi."""
        meeting = self.get_object()
        item = get_object_or_404(MeetingAgendaItem, id=item_id, meeting=meeting)

        if item.recurring_item_id:
            return Response({"detail": "Bu band allaqachon doimiy deb belgilangan"}, status=400)

        from django.utils import timezone as tz
        year = tz.now().year

        recurring = RecurringMeetingItem.objects.create(
            content=item.content,
            meeting_type=meeting.meeting_type,
            valid_year=year,
            created_by=request.user,
            is_active=True,
        )
        item.recurring_item = recurring
        item.save(update_fields=["recurring_item"])

        return Response(MeetingAgendaItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>\d+)/unset-recurring")
    def unset_recurring(self, request, pk=None, item_id=None):
        """Doimiy bandni o'chirib qo'yish (is_active=False)."""
        meeting = self.get_object()
        item = get_object_or_404(MeetingAgendaItem, id=item_id, meeting=meeting)

        if not item.recurring_item_id:
            return Response({"detail": "Bu band doimiy emas"}, status=400)

        recurring = item.recurring_item
        recurring.is_active = False
        recurring.save(update_fields=["is_active"])
        item.recurring_item = None
        item.save(update_fields=["recurring_item"])

        return Response(MeetingAgendaItemSerializer(item).data)

    @action(detail=False, methods=["get"], url_path="aggregate-stats")
    def aggregate_stats(self, request):
        """Barcha majlis topshiriqlari bo'yicha umumiy statistika."""
        from django.utils import timezone as tz
        now = tz.now()

        tasks = Task.objects.filter(meeting__isnull=False)

        done_statuses = ["APPROVED", "CLOSED"]

        total     = tasks.count()
        completed = tasks.filter(status__in=done_statuses).count()
        overdue   = tasks.filter(
            deadline__isnull=False,
            deadline__lt=now,
        ).exclude(status__in=done_statuses).count()
        # Jarayonda = bajarilmagan va muddati hali o'tmagan
        in_progress = total - completed - overdue
        late_done  = tasks.filter(
            submitted_at__isnull=False,
            deadline__isnull=False,
            submitted_at__gt=F("deadline"),
        ).count()

        return Response({
            "total":       total,
            "in_progress": in_progress,
            "completed":   completed,
            "overdue":     overdue,
            "late_done":   late_done,
        })

    @action(detail=True, methods=["get"], url_path="statistics")
    def statistics(self, request, pk=None):
        """Majlis bo'yicha statistika (faqat super admin).

        Mantiq (is_overdue fieldiga tayanmaydi — to'g'ridan DB fieldlari):
          - late_done      : submitted_at > deadline  (kech topshirilgan)
          - overdue_pending: deadline < now AND submitted_at IS NULL (hali topshirilmagan)
        """
        if not request.user.is_super_admin():
            return Response({"detail": "Ruxsat yo'q"}, status=403)

        meeting = self.get_object()
        tasks = Task.objects.filter(meeting=meeting).select_related(
            "target_department", "target_organization"
        )

        from django.db.models import F
        now = timezone.now()

        total     = tasks.count()
        completed = tasks.filter(status__in=["APPROVED", "CLOSED"]).count()

        # Kechikib bajarilgan: submitted_at mavjud va deadline dan keyin yuborilgan
        late_done = tasks.filter(
            submitted_at__isnull=False,
            deadline__isnull=False,
            submitted_at__gt=F("deadline"),
        ).count()

        # Muddati o'tgan: deadline o'tgan va hali APPROVED/CLOSED emas
        overdue_pending = tasks.filter(
            deadline__isnull=False,
            deadline__lt=now,
        ).exclude(status__in=["APPROVED", "CLOSED"]).count()

        # Har bir task uchun birinchi primary assignee ni olib, uning bo'lim/kafedra/lavozimini aniqlaymiz
        all_assignees = (
            TaskAssignee.objects
            .filter(task__meeting=meeting)
            .select_related("task", "department", "chair", "user")
            .prefetch_related("user__role_assignments__chair", "user__role_assignments__department")
            .order_by("task_id", "-is_primary", "-is_leader", "id")
        )

        # Har task uchun faqat bitta (primary) assignee ni olamiz
        task_assignee: dict[int, "TaskAssignee"] = {}
        for a in all_assignees:
            if a.task_id not in task_assignee:
                task_assignee[a.task_id] = a

        def _unit_name(a) -> str:
            if a.department_id:
                return a.department.name
            if a.chair_id:
                return a.chair.name
            role = (
                a.user.role_assignments
                .filter(is_active=True)
                .select_related("chair", "department")
                .order_by("-is_institute_leader", "-is_branch_leader", "-is_head")
                .first()
            )
            if role and role.chair:
                return role.chair.name
            if role and role.department:
                return role.department.name
            if role:
                return role.custom_role_name or role.get_role_display()
            return a.user.full_name

        dept_merged: dict[str, dict] = {}
        for task_id, a in task_assignee.items():
            t = a.task
            name = _unit_name(a)
            is_done = t.status in ("APPROVED", "CLOSED")
            is_late = (t.submitted_at and t.deadline and t.submitted_at > t.deadline)
            is_overdue_p = (
                t.deadline and t.deadline < now and not t.submitted_at
                and t.status not in ("APPROVED", "CLOSED")
            )
            if name not in dept_merged:
                dept_merged[name] = {"name": name, "total": 0, "done": 0, "late_done": 0, "overdue_pending": 0, "tasks": []}
            dept_merged[name]["total"] += 1
            if is_done:
                dept_merged[name]["done"] += 1
            if is_late:
                dept_merged[name]["late_done"] += 1
            if is_overdue_p:
                dept_merged[name]["overdue_pending"] += 1
            dept_merged[name]["tasks"].append({
                "id":       t.id,
                "title":    t.title,
                "status":   t.status,
                "deadline": t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else None,
                "assignee": a.user.full_name,
            })

        by_department = sorted(dept_merged.values(), key=lambda x: -x["total"])

        # ── Ijrochilar tashkiloti bo'yicha ────────────────────────────────────
        org_all_assignees = (
            TaskAssignee.objects
            .filter(task__meeting=meeting)
            .select_related("task", "organization", "user")
            .order_by("task_id", "-is_primary", "-is_leader", "id")
        )
        org_task_assignee: dict[int, "TaskAssignee"] = {}
        for a in org_all_assignees:
            if a.task_id not in org_task_assignee:
                org_task_assignee[a.task_id] = a

        org_merged: dict[str, dict] = {}
        for task_id, a in org_task_assignee.items():
            t = a.task
            name = a.organization.name if a.organization_id else "Noma'lum"
            is_done = t.status in ("APPROVED", "CLOSED")
            is_late = (t.submitted_at and t.deadline and t.submitted_at > t.deadline)
            is_overdue_p = (
                t.deadline and t.deadline < now and not t.submitted_at
                and t.status not in ("APPROVED", "CLOSED")
            )
            if name not in org_merged:
                org_merged[name] = {"name": name, "total": 0, "done": 0, "late_done": 0, "overdue_pending": 0, "tasks": []}
            org_merged[name]["total"] += 1
            if is_done:
                org_merged[name]["done"] += 1
            if is_late:
                org_merged[name]["late_done"] += 1
            if is_overdue_p:
                org_merged[name]["overdue_pending"] += 1
            org_merged[name]["tasks"].append({
                "id":       t.id,
                "title":    t.title,
                "status":   t.status,
                "deadline": t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else None,
                "assignee": a.user.full_name,
            })

        by_organization = sorted(org_merged.values(), key=lambda x: -x["total"])

        def _assignee_label(task):
            a = task.assignees.select_related("department", "chair", "user").first()
            if not a:
                return "—"
            if a.department_id:
                return f"{a.user.full_name} ({a.department.name})"
            if a.chair_id:
                return f"{a.user.full_name} ({a.chair.name})"
            return a.user.full_name

        late_done_list = [
            {
                "id":       t.id,
                "title":    t.title,
                "deadline": t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else None,
                "assignee": _assignee_label(t),
            }
            for t in tasks.filter(
                submitted_at__isnull=False,
                deadline__isnull=False,
                submitted_at__gt=F("deadline"),
            ).prefetch_related("assignees__department", "assignees__chair", "assignees__user")
            .order_by("deadline")
        ]

        overdue_list = [
            {
                "id":       t.id,
                "title":    t.title,
                "deadline": t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else None,
                "assignee": _assignee_label(t),
            }
            for t in tasks.filter(
                deadline__isnull=False,
                deadline__lt=now,
                submitted_at__isnull=True,
            ).exclude(status__in=["APPROVED", "CLOSED"])
            .prefetch_related("assignees__department", "assignees__chair", "assignees__user")
            .order_by("deadline")
        ]

        return Response({
            "total":           total,
            "completed":       completed,
            "late_done":       late_done,
            "overdue_pending": overdue_pending,
            "by_department":   by_department,
            "by_organization": by_organization,
            "late_done_list":  late_done_list,
            "overdue_list":    overdue_list,
        })


# ── Doimiy bandlar ViewSet ──────────────────────────────────────────────────

class RecurringMeetingItemViewSet(viewsets.ModelViewSet):
    """
    Doimiy bandlar ro'yxati.
    GET    /tasks/recurring/                        — faol doimiy bandlar
    GET    /tasks/recurring/?meeting_type=REKTORAT&year=2026
    DELETE /tasks/recurring/{id}/                   — doimiy bandni o'chirish
    """
    permission_classes = [IsAuthenticated, CanCreateTask]
    serializer_class   = RecurringMeetingItemSerializer
    http_method_names  = ["get", "delete", "head", "options"]

    def get_queryset(self):
        from django.utils import timezone as tz
        qs = RecurringMeetingItem.objects.filter(is_active=True)
        meeting_type = self.request.query_params.get("meeting_type")
        year = self.request.query_params.get("year", tz.now().year)
        if meeting_type:
            qs = qs.filter(meeting_type=meeting_type)
        qs = qs.filter(valid_year=int(year))
        return qs.select_related("created_by")

    def destroy(self, request, *args, **kwargs):
        """O'chirish — is_active=False qiladi (bazadan o'chmaydi)."""
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
