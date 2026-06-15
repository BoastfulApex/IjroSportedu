from rest_framework import serializers
from .models import Order, OrderItem, OrderItemApprover, OrderAttachment, OrderItemAcknowledgment
from apps.tasks.serializers import TaskAssigneeSerializer


class OrderItemAcknowledgmentSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model  = OrderItemAcknowledgment
        fields = ["id", "user", "user_full_name", "viewed_at", "accepted_at"]


class OrderAttachmentSerializer(serializers.ModelSerializer):
    file_url           = serializers.SerializerMethodField()
    uploaded_by_name   = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model  = OrderAttachment
        fields = ["id", "original_name", "file_url", "uploaded_by_name", "uploaded_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class OrderItemApproverSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model  = OrderItemApprover
        fields = ["id", "user", "user_full_name", "has_approved", "approved_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    responsible_name         = serializers.CharField(source="responsible.full_name", read_only=True)
    task_id                  = serializers.IntegerField(source="task.id", read_only=True)
    task_status              = serializers.CharField(source="task.status", read_only=True)
    task_title               = serializers.CharField(source="task.title", read_only=True)
    task_deadline            = serializers.DateTimeField(source="task.deadline", read_only=True)
    task_priority            = serializers.CharField(source="task.priority", read_only=True)
    task_is_malumot          = serializers.BooleanField(source="task.is_malumot", read_only=True)
    task_creating_department = serializers.IntegerField(source="task.creating_department_id", read_only=True)
    task_target_department   = serializers.IntegerField(source="task.target_department_id", read_only=True)
    task_valid_transitions   = serializers.SerializerMethodField()
    task_assignees           = serializers.SerializerMethodField()
    approvers                = OrderItemApproverSerializer(many=True, read_only=True)
    acknowledgments          = OrderItemAcknowledgmentSerializer(many=True, read_only=True)
    is_created               = serializers.SerializerMethodField()
    all_approved             = serializers.SerializerMethodField()
    order_id                 = serializers.IntegerField(source="order.id", read_only=True)
    order_number             = serializers.CharField(source="order.number", read_only=True)
    order_title              = serializers.CharField(source="order.title", read_only=True)
    order_type               = serializers.CharField(source="order.order_type", read_only=True)

    class Meta:
        model  = OrderItem
        fields = [
            "id", "band_number", "content", "deadline", "item_type",
            "responsible", "responsible_name",
            "task_id", "task_title", "task_status", "task_deadline",
            "task_priority", "task_is_malumot",
            "task_creating_department", "task_target_department", "task_valid_transitions",
            "task_assignees",
            "approvers", "acknowledgments", "is_created", "all_approved",
            "order_id", "order_number", "order_title", "order_type",
        ]

    def get_task_valid_transitions(self, obj):
        if not obj.task_id:
            return []
        from apps.tasks.models import Task
        return Task.VALID_TRANSITIONS.get(obj.task.status, [])

    def get_is_created(self, obj):
        if obj.item_type == OrderItem.ItemType.KELISHISH:
            return obj.approvers.exists()
        return obj.task_id is not None

    def get_all_approved(self, obj):
        if obj.item_type != OrderItem.ItemType.KELISHISH:
            return None
        approvers = list(obj.approvers.all())
        if not approvers:
            return False
        return all(a.has_approved for a in approvers)

    def get_task_assignees(self, obj):
        if not obj.task_id:
            return []
        return TaskAssigneeSerializer(obj.task.assignees.all(), many=True).data


class OrderSerializer(serializers.ModelSerializer):
    items              = OrderItemSerializer(many=True, read_only=True)
    created_by_name    = serializers.CharField(source="created_by.full_name", read_only=True)
    items_count        = serializers.IntegerField(source="items.count", read_only=True)
    created_count      = serializers.SerializerMethodField()
    order_type_display = serializers.CharField(source="get_order_type_display", read_only=True)
    attachments        = OrderAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model  = Order
        fields = [
            "id", "number", "title", "date", "description",
            "order_type", "order_type_display",
            "is_confirmed", "created_by", "created_by_name",
            "created_at", "items_count", "created_count", "items",
            "attachments",
        ]
        read_only_fields = ["created_by", "is_confirmed", "created_at"]

    def get_created_count(self, obj):
        return obj.items.filter(task__isnull=False).count()


class OrderListSerializer(serializers.ModelSerializer):
    created_by_name    = serializers.CharField(source="created_by.full_name", read_only=True)
    items_count        = serializers.IntegerField(source="items.count", read_only=True)
    created_count      = serializers.SerializerMethodField()
    order_type_display = serializers.CharField(source="get_order_type_display", read_only=True)
    attachments        = OrderAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model  = Order
        fields = [
            "id", "number", "title", "date", "description",
            "order_type", "order_type_display",
            "is_confirmed", "created_by_name", "created_at",
            "items_count", "created_count", "attachments",
        ]

    def get_created_count(self, obj):
        return obj.items.filter(task__isnull=False).count()


class OrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrderItem
        fields = ["id", "band_number", "content", "deadline", "responsible", "item_type"]
