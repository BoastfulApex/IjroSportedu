from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from django.utils import timezone
from apps.tasks.models import Task, TaskAssignee
from apps.accounts.permissions import CanCreateTask, CanCreateOrder
from apps.accounts.models import UserRoleAssignment
from .models import Order, OrderItem, OrderItemApprover, OrderAttachment, OrderItemAcknowledgment
from .serializers import (
    OrderSerializer, OrderListSerializer,
    OrderItemSerializer, OrderItemCreateSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Buyruqlar CRUD + band qo'shish/o'chirish + tasdiqlash.
    Tasdiqlash → IJRO bandlar uchun Task, KELISHISH bandlar uchun kelishuvchilar yaratiladi.
    """
    parser_classes = [JSONParser]

    def get_permissions(self):
        # Oddiy xodimlar ham ro'yxat va ko'rish uchun faqat login kerak
        if self.action in ["retrieve", "approve_item", "list"]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), CanCreateOrder()]

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_super_admin():
            return Response({"detail": "Faqat super admin o'chira oladi"}, status=403)
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        from django.db.models import Q
        qs = Order.objects.prefetch_related(
            "items__task__assignees__user",
            "items__task__assignees__department",
            "items__task__assignees__chair",
            "items__task__creating_department",
            "items__task__target_department",
            "items__approvers__user",
            "items__acknowledgments__user",
            "attachments__uploaded_by",
        ).select_related("created_by")
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_super_admin() or user.is_task_controller():
            return qs
        if user.is_institute_leader() or user.is_branch_leader():
            return qs
        if user.is_scientific_council_secretary():
            return qs.filter(
                Q(order_type=Order.OrderType.ILMIY_KENGASH) |
                Q(items__approvers__user=user)
            ).distinct()
        has_order_perm = UserRoleAssignment.objects.filter(
            user=user, is_active=True,
        ).filter(
            Q(department__dept_type="ORDER_CONTROL") |
            Q(department__dept_type="TASK_CONTROL") |
            Q(can_create_tasks=True) |
            Q(department__can_create_tasks=True)
        ).exists()
        if has_order_perm:
            return qs
        # Xodim: o'ziga biriktirilgan (mas'ul yoki task ijrochi) yoki kelishuvchi
        return qs.filter(
            Q(items__responsible=user) |
            Q(items__task__assignees__user=user) |
            Q(items__approvers__user=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        """Buyruqni ochganda ijrochiga 'viewed_at' avtomatik belgilanadi."""
        instance = self.get_object()
        user = request.user
        now = timezone.now()
        # IJRO va MALUMOT bandlari uchun, task assignee bo'lsa
        for item in instance.items.filter(
            item_type__in=[OrderItem.ItemType.IJRO, OrderItem.ItemType.MALUMOT],
            task__isnull=False
        ):
            if item.task.assignees.filter(user=user).exists():
                OrderItemAcknowledgment.objects.update_or_create(
                    item=item, user=user,
                    defaults={"viewed_at": now},
                )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ── Bandlar ────────────────────────────────────────────────────
    @action(detail=True, methods=["get", "post"], url_path="items")
    def items(self, request, pk=None):
        order = self.get_object()

        if request.method == "GET":
            return Response(OrderItemSerializer(order.items.all(), many=True).data)

        if not CanCreateOrder().has_permission(request, self):
            return Response({"detail": "Ruxsat yo'q"}, status=403)

        if order.is_confirmed:
            return Response({"detail": "Buyruq tasdiqlangan, band qo'shib bo'lmaydi"}, status=400)

        serializer = OrderItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(order=order)
        return Response(OrderItemSerializer(item).data, status=201)

    @action(detail=True, methods=["patch", "delete"], url_path=r"items/(?P<item_id>\d+)")
    def item_detail(self, request, pk=None, item_id=None):
        order = self.get_object()
        try:
            item = order.items.get(id=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Band topilmadi"}, status=404)

        if order.is_confirmed:
            return Response({"detail": "Buyruq tasdiqlangan, o'zgartirish mumkin emas"}, status=400)

        if request.method == "DELETE":
            item.delete()
            return Response(status=204)

        serializer = OrderItemCreateSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(OrderItemSerializer(item).data)

    # ── Buyruq ilovalarini yuklash ─────────────────────────────────
    @action(detail=True, methods=["post"], url_path="upload-file",
            parser_classes=[MultiPartParser, FormParser])
    def upload_file(self, request, pk=None):
        order = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl tanlanmagan"}, status=400)
        att = OrderAttachment.objects.create(
            order=order,
            file=file,
            original_name=file.name,
            uploaded_by=request.user,
        )
        from .serializers import OrderAttachmentSerializer
        return Response(
            OrderAttachmentSerializer(att, context={"request": request}).data,
            status=201,
        )

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<att_id>\d+)")
    def delete_attachment(self, request, pk=None, att_id=None):
        order = self.get_object()
        try:
            att = order.attachments.get(id=att_id)
        except OrderAttachment.DoesNotExist:
            return Response({"detail": "Ilova topilmadi"}, status=404)
        att.file.delete(save=False)
        att.delete()
        return Response(status=204)

    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<att_id>\d+)/download",
            permission_classes=[])
    def download_attachment(self, request, pk=None, att_id=None):
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from django.contrib.auth.models import AnonymousUser
        token = request.query_params.get("token")
        if token:
            try:
                auth = JWTAuthentication()
                validated = auth.get_validated_token(token)
                request._user = auth.get_user(validated)
            except (InvalidToken, TokenError):
                request._user = AnonymousUser()
        if not (request.user and request.user.is_authenticated):
            return Response({"detail": "Autentifikatsiya talab etiladi"}, status=401)
        order = get_object_or_404(Order, pk=pk)
        try:
            att = order.attachments.get(id=att_id)
        except OrderAttachment.DoesNotExist:
            return Response({"detail": "Ilova topilmadi"}, status=404)
        from django.http import FileResponse
        return FileResponse(
            att.file.open("rb"),
            as_attachment=True,
            filename=att.original_name or att.file.name.split("/")[-1],
        )

    # ── Excel dan bandlarni yuklash ────────────────────────────────
    @action(detail=True, methods=["post"], url_path="upload-excel",
            parser_classes=[MultiPartParser, FormParser])
    def upload_excel(self, request, pk=None):
        """
        Excel fayl formati (2 ustun):
        | Band raqami | Topshiriq mazmuni |
        |-------------|-------------------|
        | 1           | ...               |
        """
        order = self.get_object()
        if order.is_confirmed:
            return Response({"detail": "Buyruq tasdiqlangan, o'zgartirish mumkin emas"}, status=400)

        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "Fayl yuborilmadi"}, status=400)

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

        # Topshiriqsiz bandlarni o'chir, yangilarini yoz
        order.items.filter(task__isnull=True).delete()

        created = []
        for item in items_data:
            obj, _ = OrderItem.objects.get_or_create(
                order=order,
                band_number=item["band_number"],
                defaults={"content": item["content"]},
            )
            created.append(obj)

        return Response(OrderItemSerializer(created, many=True).data)

    # ── Tasdiqlash — har bir band uchun Task yaratish ──────────────
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
            }
          ]
        }
        """
        order = self.get_object()
        if order.is_confirmed:
            return Response({"detail": "Buyruq allaqachon tasdiqlangan"}, status=400)

        items_payload = request.data.get("items", [])
        if not items_payload:
            return Response({"detail": "Bandlar ro'yxati bo'sh"}, status=400)

        from apps.organizations.models import Organization, Department
        from apps.accounts.models import UserRoleAssignment

        user = request.user
        if user.is_super_admin() or user.is_task_controller():
            creating_dept = None
        else:
            from django.db.models import Q
            assignment = UserRoleAssignment.objects.filter(
                user=user, is_active=True
            ).filter(
                Q(department__can_create_tasks=True) | Q(department__dept_type="TASK_CONTROL")
            ).select_related("department").first()
            creating_dept = assignment.department if assignment else None

        errors = []
        created_tasks = []

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        for payload in items_payload:
            item_id = payload.get("id")
            try:
                item = order.items.get(id=item_id)
            except OrderItem.DoesNotExist:
                errors.append(f"Band #{item_id} topilmadi")
                continue

            # ── KELISHISH bandi (eski, orqaga moslik) ───────────────
            if item.item_type == OrderItem.ItemType.KELISHISH:
                if item.approvers.exists():
                    continue
                approvers_data = payload.get("approvers", [])
                for a in approvers_data:
                    uid = a.get("user")
                    if not uid:
                        continue
                    try:
                        approver_user = UserModel.objects.get(id=uid)
                    except UserModel.DoesNotExist:
                        continue
                    OrderItemApprover.objects.get_or_create(
                        item=item,
                        user=approver_user,
                        defaults={"added_by": user},
                    )
                created_tasks.append(f"kelishish-{item.id}")
                continue

            # ── IJRO va MALUMOT bandlari — task yaratiladi ───────────
            if item.task:
                continue  # allaqachon yaratilgan

            deadline_raw = payload.get("deadline")
            if deadline_raw:
                from django.utils.dateparse import parse_datetime
                from django.utils import timezone as tz
                deadline = parse_datetime(deadline_raw)
                if deadline and tz.is_naive(deadline):
                    deadline = tz.make_aware(deadline)
            else:
                deadline = None
            priority       = payload.get("priority", Task.Priority.MEDIUM)
            target_org_id  = payload.get("target_organization")
            target_dept_id = payload.get("target_department")
            assignees_data = payload.get("assignees", [])

            if not target_org_id:
                errors.append(f"Band #{item.band_number}: target_organization majburiy")
                continue

            try:
                target_org = Organization.objects.get(id=target_org_id)
            except Organization.DoesNotExist:
                errors.append(f"Band #{item.band_number}: tashkilot topilmadi")
                continue

            target_dept = None
            if target_dept_id:
                try:
                    target_dept = Department.objects.get(id=target_dept_id)
                except Department.DoesNotExist:
                    pass

            task_type_map = {
                Order.OrderType.ILMIY_KENGASH: Task.TaskType.ILMIY_KENGASH,
            }
            task_type = task_type_map.get(order.order_type, Task.TaskType.REKTORAT)

            task = Task.objects.create(
                title=f"Buyruq №{order.number} — {item.band_number}-band: {item.content[:100]}",
                description=item.content,
                priority=priority,
                task_type=task_type,
                creator=user,
                creating_department=creating_dept,
                target_organization=target_org,
                target_department=target_dept,
                deadline=deadline or item.deadline,
                is_malumot=(item.item_type == OrderItem.ItemType.MALUMOT),
            )

            for a in assignees_data:
                uid = a.get("user")
                if not uid:
                    continue
                try:
                    assignee_user = UserModel.objects.get(id=uid)
                except UserModel.DoesNotExist:
                    continue
                TaskAssignee.objects.create(
                    task=task,
                    user=assignee_user,
                    organization_id=a.get("organization"),
                    department_id=a.get("department"),
                    chair_id=a.get("chair"),
                    is_primary=a.get("is_primary", False),
                    is_leader=a.get("is_leader", False),
                    assigned_by=user,
                )

            if task.assignees.exists():
                task.status = Task.Status.ASSIGNED
                task.save(update_fields=["status"])

            item.task = task
            item.save(update_fields=["task"])
            created_tasks.append(task.id)

        if not errors:
            order.is_confirmed = True
            order.save(update_fields=["is_confirmed"])

        return Response(
            {
                "detail": f"{len(created_tasks)} ta band bajarildi",
                "errors": errors,
                "order": OrderSerializer(order, context={"request": request}).data,
            }
        )

    # ── Barcha buyruq topshiriqlari — nazorat uchun ───────────────
    @action(detail=False, methods=["get"], url_path="all-tasks")
    def all_tasks(self, request):
        """Barcha buyruq bandlari nazorati — faqat ruxsat etilgan foydalanuvchilar uchun."""
        user = request.user
        from django.db.models import Q
        has_perm = (
            user.is_super_admin() or
            user.is_task_controller() or
            user.is_scientific_council_secretary() or
            UserRoleAssignment.objects.filter(
                user=user, is_active=True,
            ).filter(
                Q(department__dept_type="ORDER_CONTROL") |
                Q(department__dept_type="TASK_CONTROL") |
                Q(can_create_tasks=True) |
                Q(department__can_create_tasks=True)
            ).exists()
        )
        if not has_perm:
            return Response({"detail": "Ruxsat yo'q"}, status=403)

        items = OrderItem.objects.filter(
            task__isnull=False,
        ).select_related(
            "order", "task",
            "task__creating_department", "task__target_department",
        ).prefetch_related(
            "task__assignees__user",
            "task__assignees__department",
            "acknowledgments__user",
        ).order_by("-order__date", "band_number")

        from .serializers import OrderItemSerializer
        return Response(OrderItemSerializer(items, many=True, context={"request": request}).data)

    # ── Mening buyruq topshiriqlarim ──────────────────────────────
    @action(detail=False, methods=["get"], url_path="my-tasks")
    def my_tasks(self, request):
        """Joriy foydalanuvchi ijrochi bo'lgan barcha buyruq bandlari."""
        from apps.tasks.models import Task
        user = request.user
        items = OrderItem.objects.filter(
            task__isnull=False,
            task__assignees__user=user,
        ).exclude(
            task__status=Task.Status.CLOSED,
        ).select_related(
            "order", "task",
        ).prefetch_related(
            "task__assignees__user",
            "task__assignees__department",
            "acknowledgments",
        ).distinct().order_by("-order__date", "band_number")
        from .serializers import OrderItemSerializer
        return Response(OrderItemSerializer(items, many=True, context={"request": request}).data)

    # ── Ijrochi "Qabul qilish" tugmasi ────────────────────────────
    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>\d+)/accept")
    def accept_item(self, request, pk=None, item_id=None):
        order = self.get_object()
        try:
            item = order.items.get(id=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Band topilmadi"}, status=404)

        if item.item_type != OrderItem.ItemType.IJRO:
            return Response({"detail": "Bu band ijro uchun emas"}, status=400)

        if not item.task or not item.task.assignees.filter(user=request.user).exists():
            return Response({"detail": "Siz bu bandning ijrochisi emassiz"}, status=403)

        now = timezone.now()
        ack, _ = OrderItemAcknowledgment.objects.get_or_create(
            item=item, user=request.user,
            defaults={"viewed_at": now},
        )
        if ack.accepted_at:
            return Response({"detail": "Allaqachon qabul qilgansiz"}, status=400)
        ack.accepted_at = now
        if not ack.viewed_at:
            ack.viewed_at = now
        ack.save(update_fields=["accepted_at", "viewed_at"])
        return Response(OrderItemSerializer(item, context={"request": request}).data)

    # ── Ma'lumot uchun qabul qilish (task CLOSED ga o'tadi) ─────────
    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>\d+)/accept-malumot")
    def accept_malumot(self, request, pk=None, item_id=None):
        order = self.get_object()
        try:
            item = order.items.get(id=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Band topilmadi"}, status=404)

        if item.item_type != OrderItem.ItemType.MALUMOT:
            return Response({"detail": "Bu band ma'lumot uchun emas"}, status=400)

        if not item.task or not item.task.assignees.filter(user=request.user).exists():
            return Response({"detail": "Siz bu bandning ijrochisi emassiz"}, status=403)

        if item.task.status == Task.Status.CLOSED:
            return Response({"detail": "Allaqachon yopilgan"}, status=400)

        now = timezone.now()
        item.task.status = Task.Status.CLOSED
        item.task._actor = request.user
        item.task.save()

        OrderItemAcknowledgment.objects.update_or_create(
            item=item, user=request.user,
            defaults={"viewed_at": now, "accepted_at": now},
        )
        return Response(OrderItemSerializer(item, context={"request": request}).data)

    # ── Kelishuvchi "Roziman" tugmasi ──────────────────────────────
    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>\d+)/approve")
    def approve_item(self, request, pk=None, item_id=None):
        order = self.get_object()
        try:
            item = order.items.get(id=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Band topilmadi"}, status=404)

        if item.item_type != OrderItem.ItemType.KELISHISH:
            return Response({"detail": "Bu band kelishish uchun emas"}, status=400)

        try:
            approver = item.approvers.get(user=request.user)
        except OrderItemApprover.DoesNotExist:
            return Response({"detail": "Siz kelishuvchilar ro'yxatida emassiz"}, status=403)

        if approver.has_approved:
            return Response({"detail": "Siz allaqachon rozilik bildingiz"}, status=400)

        approver.has_approved = True
        approver.approved_at  = timezone.now()
        approver.save(update_fields=["has_approved", "approved_at"])

        return Response(OrderItemSerializer(item, context={"request": request}).data)
