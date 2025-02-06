from __future__ import annotations

from notifications.views import NotificationsViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'notification', NotificationsViewSet, basename='notifications')

urlpatterns = router.urls
