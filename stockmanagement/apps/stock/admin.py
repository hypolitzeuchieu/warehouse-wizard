from __future__ import annotations

from apps.stock.models import Category
from apps.stock.models import Product
from apps.stock.models import Stock
from apps.stock.models import StockMovement
from apps.stock.models import SubCategory
from django.contrib import admin


admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Stock)
admin.site.register(SubCategory)
admin.site.register(StockMovement)
