from __future__ import annotations

from apps.reports.models import InventoryReport
from apps.reports.models import Invoice
from apps.reports.models import InvoiceArchive
from apps.reports.models import InvoiceArchiveLine
from apps.reports.models import InvoiceLine
from apps.reports.models import Report
from apps.reports.models import SalesReport
from django.contrib import admin

admin.site.register(Invoice)
admin.site.register(InvoiceLine)
admin.site.register(Report)
admin.site.register(InvoiceArchive)
admin.site.register(InvoiceArchiveLine)
admin.site.register(InventoryReport)
admin.site.register(SalesReport)
