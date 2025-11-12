from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.reports.views import (
    ArchiveInvoiceVieSet,
    ExpenseViewSet,
    GeneralReportViewSet,
    InvoiceViewSet,
)

router = DefaultRouter()
router.register(r"invoice", InvoiceViewSet, basename="invoice")
router.register(r"archive", ArchiveInvoiceVieSet, basename="archive-invoice")
router.register(r"report", GeneralReportViewSet, basename="generate-report")
router.register(r"expense", ExpenseViewSet, basename="expense")

urlpatterns = router.urls
