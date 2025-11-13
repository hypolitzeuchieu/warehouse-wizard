from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.dashboard.views import DashboardViewSet

router = DefaultRouter()
router.register(r"dashboard", DashboardViewSet, basename="dashboard")

urlpatterns = router.urls
