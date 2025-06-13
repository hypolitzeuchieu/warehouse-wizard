from __future__ import annotations

from reports.views import ArchiveInvoiceVieSet
from reports.views import ExpenseViewSet
from reports.views import GeneralReportViewSet
from reports.views import InvoiceViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'invoice', InvoiceViewSet, basename='invoice')
router.register(r'archive', ArchiveInvoiceVieSet, basename='archive-invoice')
router.register(r'report', GeneralReportViewSet, basename='generate-report')
router.register(r'expense', ExpenseViewSet, basename='expense')

urlpatterns = router.urls
