from __future__ import annotations

from reports.views import ReportsViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'report', ReportsViewSet, basename='report-inventory')

urlpatterns = router.urls
