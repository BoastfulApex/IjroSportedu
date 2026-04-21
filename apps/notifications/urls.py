from django.urls import path
from .views import NotificationListView, NotificationMarkReadView, mark_all_read, unread_count

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications-list"),
    path("unread-count/", unread_count, name="notifications-unread-count"),
    path("read-all/", mark_all_read, name="notifications-read-all"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification-read"),
]
