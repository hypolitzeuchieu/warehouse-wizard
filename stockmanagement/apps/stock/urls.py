from __future__ import annotations

from rest_framework.routers import DefaultRouter

from apps.stock.views import CategoryViewSet, ProductViewSet, StockViewSet

router = DefaultRouter()
router.register(r"stock", StockViewSet, basename="stocks")
router.register(r"product", ProductViewSet, basename="products")
router.register(r"categories", CategoryViewSet, basename="")

urlpatterns = router.urls
