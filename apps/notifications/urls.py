from django.urls import path
from .views import (
    NotificationListView, NotificationMarkReadView,
    mark_all_read, unread_count, recent_notifications,
    vapid_public_key, push_subscribe, push_unsubscribe,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications-list"),
    path("unread-count/", unread_count, name="notifications-unread-count"),
    path("recent/", recent_notifications, name="notifications-recent"),
    path("read-all/", mark_all_read, name="notifications-read-all"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification-read"),
    # Web Push
    path("push/vapid-key/", vapid_public_key, name="vapid-public-key"),
    path("push/subscribe/", push_subscribe, name="push-subscribe"),
    path("push/unsubscribe/", push_unsubscribe, name="push-unsubscribe"),
]
