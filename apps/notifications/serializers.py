from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    notif_type_display = serializers.CharField(source="get_notif_type_display", read_only=True)
    task_title = serializers.CharField(source="related_task.title", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "title", "message", "notif_type", "notif_type_display",
            "related_task", "task_title", "is_read", "created_at",
        ]
        read_only_fields = ["id", "title", "message", "notif_type", "related_task", "created_at"]
