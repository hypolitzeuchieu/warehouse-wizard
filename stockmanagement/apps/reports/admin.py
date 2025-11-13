from __future__ import annotations

from django.contrib import admin

from apps.reports.models import (
    InventoryReport,
    Invoice,
    InvoiceArchive,
    InvoiceArchiveLine,
    InvoiceLine,
    Report,
    SalesReport,
)

admin.site.register(Invoice)
admin.site.register(InvoiceLine)
admin.site.register(Report)
admin.site.register(InvoiceArchive)
admin.site.register(InvoiceArchiveLine)
admin.site.register(InventoryReport)
admin.site.register(SalesReport)
