from __future__ import annotations

from apps.reports.views import ArchiveInvoiceVieSet
from apps.reports.views import ExpenseViewSet
from apps.reports.views import GeneralReportViewSet
from apps.reports.views import InvoiceViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'invoice', InvoiceViewSet, basename='invoice')
router.register(r'archive', ArchiveInvoiceVieSet, basename='archive-invoice')
router.register(r'report', GeneralReportViewSet, basename='generate-report')
router.register(r'expense', ExpenseViewSet, basename='expense')

urlpatterns = router.urls
