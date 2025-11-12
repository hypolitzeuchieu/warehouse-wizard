from __future__ import annotations

from django.contrib import admin

from apps.stock.models import Category, Product, Stock, StockMovement, SubCategory

admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Stock)
admin.site.register(SubCategory)
admin.site.register(StockMovement)
