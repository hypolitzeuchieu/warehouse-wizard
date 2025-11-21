"""ViewSets package."""

from presentation.viewsets.business_viewset import BusinessViewSet
from presentation.viewsets.category_viewset import CategoryViewSet
from presentation.viewsets.customer_viewset import CustomerViewSet
from presentation.viewsets.finance_viewset import FinanceViewSet
from presentation.viewsets.inventory_viewset import InventoryViewSet
from presentation.viewsets.notification_viewset import NotificationViewSet
from presentation.viewsets.sales_viewset import SalesViewSet
from presentation.viewsets.subcategory_viewset import SubCategoryViewSet

__all__ = [
    "BusinessViewSet",
    "CategoryViewSet",
    "CustomerViewSet",
    "FinanceViewSet",
    "InventoryViewSet",
    "NotificationViewSet",
    "SalesViewSet",
    "SubCategoryViewSet",
]
