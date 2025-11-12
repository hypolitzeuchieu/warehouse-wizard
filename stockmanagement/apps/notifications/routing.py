from __future__ import annotations

from django.urls import re_path

from apps.notifications.consumer import NotificationConsumer

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
]
