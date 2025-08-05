from __future__ import annotations

from apps.stock.views import CategoryViewSet
from apps.stock.views import ProductViewSet
from apps.stock.views import StockViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'stock', StockViewSet, basename='stocks')
router.register(r'product', ProductViewSet, basename='products')
router.register(r'categories', CategoryViewSet, basename='')

urlpatterns = router.urls
