from __future__ import annotations

from rest_framework.routers import DefaultRouter
from stock.views import StockViewSet


router = DefaultRouter()
router.register(r'stock', StockViewSet, basename='stocks')

urlpatterns = router.urls
