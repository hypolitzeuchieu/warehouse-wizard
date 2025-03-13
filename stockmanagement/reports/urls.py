from __future__ import annotations

from reports.views import ArchiveInvoiceVieSet
from reports.views import GeneralReportViewSet
from reports.views import ReportsViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'report', ReportsViewSet, basename='report-inventory')
router.register(r'archive', ArchiveInvoiceVieSet, basename='archive-invoice')
router.register(r'generate-report', GeneralReportViewSet, basename='generate-report')

urlpatterns = router.urls
