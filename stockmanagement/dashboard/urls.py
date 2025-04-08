from __future__ import annotations

from dashboard.views import DashboardViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = router.urls
