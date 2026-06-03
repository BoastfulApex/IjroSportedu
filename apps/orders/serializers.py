from rest_framework import serializers
from .models import Order, OrderItem, OrderItemApprover
from apps.tasks.serializers import TaskAssigneeSerializer


class OrderItemApproverSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model  = OrderItemApprover
        fields = ["id", "user", "user_full_name", "has_approved", "approved_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    responsible_name = serializers.CharField(source="responsible.full_name", read_only=True)
    task_id          = serializers.IntegerField(source="task.id", read_only=True)
    task_status      = serializers.CharField(source="task.status", read_only=True)
    task_title       = serializers.CharField(source="task.title", read_only=True)
    task_deadline    = serializers.DateTimeField(source="task.deadline", read_only=True)
    task_priority    = serializers.CharField(source="task.priority", read_only=True)
    task_assignees   = serializers.SerializerMethodField()
    approvers        = OrderItemApproverSerializer(many=True, read_only=True)
    is_created       = serializers.SerializerMethodField()
    all_approved     = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = [
            "id", "band_number", "content", "deadline", "item_type",
            "responsible", "responsible_name",
            "task_id", "task_title", "task_status", "task_deadline",
            "task_priority", "task_assignees",
            "approvers", "is_created", "all_approved",
        ]

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
    items           = OrderItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    items_count     = serializers.IntegerField(source="items.count", read_only=True)
    created_count   = serializers.SerializerMethodField()
    file_url        = serializers.SerializerMethodField()
    order_type_display = serializers.CharField(source="get_order_type_display", read_only=True)

    class Meta:
        model  = Order
        fields = [
            "id", "number", "title", "date", "description",
            "order_type", "order_type_display",
            "is_confirmed", "created_by", "created_by_name",
            "created_at", "items_count", "created_count", "items",
            "file_url",
        ]
        read_only_fields = ["created_by", "is_confirmed", "created_at"]

    def get_created_count(self, obj):
        return obj.items.filter(task__isnull=False).count()

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class OrderListSerializer(serializers.ModelSerializer):
    created_by_name    = serializers.CharField(source="created_by.full_name", read_only=True)
    items_count        = serializers.IntegerField(source="items.count", read_only=True)
    created_count      = serializers.SerializerMethodField()
    file_url           = serializers.SerializerMethodField()
    order_type_display = serializers.CharField(source="get_order_type_display", read_only=True)

    class Meta:
        model  = Order
        fields = [
            "id", "number", "title", "date", "description",
            "order_type", "order_type_display",
            "is_confirmed", "created_by_name", "created_at",
            "items_count", "created_count", "file_url",
        ]

    def get_created_count(self, obj):
        return obj.items.filter(task__isnull=False).count()

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class OrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrderItem
        fields = ["id", "band_number", "content", "deadline", "responsible", "item_type"]
