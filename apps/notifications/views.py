from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from .models import Notification, PushSubscription
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related("related_task")
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == "true")
        return qs


class NotificationMarkReadView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        notif = self.get_object()
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notif).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({"detail": "Barcha xabarnomalar o'qildi"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({"count": count})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recent_notifications(request):
    """Oxirgi 8 ta bildirishnoma (dropdown uchun)."""
    notifs = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("related_task")
        .order_by("-created_at")[:8]
    )
    return Response(NotificationSerializer(notifs, many=True).data)


# ─── Web Push ─────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vapid_public_key(request):
    return Response({"public_key": settings.VAPID_PUBLIC_KEY})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def push_subscribe(request):
    endpoint = request.data.get("endpoint", "").strip()
    p256dh   = request.data.get("p256dh",   "").strip()
    auth     = request.data.get("auth",     "").strip()
    if not all([endpoint, p256dh, auth]):
        return Response({"detail": "endpoint, p256dh va auth kerak"}, status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": p256dh, "auth": auth},
    )
    return Response({"detail": "Obuna saqlandi"}, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def push_unsubscribe(request):
    endpoint = request.data.get("endpoint", "").strip()
    if endpoint:
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return Response({"detail": "Obuna o'chirildi"})
