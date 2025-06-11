from __future__ import annotations

from django.contrib import admin
from stock.models import Category
from stock.models import Product
from stock.models import Stock
from stock.models import StockMovement
from stock.models import SubCategory


admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Stock)
admin.site.register(SubCategory)
admin.site.register(StockMovement)
