from __future__ import annotations

from django.contrib import admin
from reports.models import InventoryReport
from reports.models import Invoice
from reports.models import InvoiceArchive
from reports.models import InvoiceArchiveLine
from reports.models import InvoiceLine
from reports.models import Report
from reports.models import SalesReport

admin.site.register(Invoice)
admin.site.register(InvoiceLine)
admin.site.register(Report)
admin.site.register(InvoiceArchive)
admin.site.register(InvoiceArchiveLine)
admin.site.register(InventoryReport)
admin.site.register(SalesReport)
