from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.notifications.views import NotificationsViewSet

router = DefaultRouter()
router.register(r"notification", NotificationsViewSet, basename="notifications")

urlpatterns = router.urls
