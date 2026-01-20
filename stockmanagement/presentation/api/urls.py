"""API URL configuration for RetailPulse."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from presentation.views import (
    auth_views,
)
from presentation.viewsets.business_viewset import BusinessViewSet
from presentation.viewsets.category_viewset import CategoryViewSet
from presentation.viewsets.customer_viewset import CustomerViewSet
from presentation.viewsets.dashboard_viewset import DashboardViewSet
from presentation.viewsets.finance_viewset import FinanceViewSet
from presentation.viewsets.inventory_viewset import InventoryViewSet
from presentation.viewsets.notification_viewset import NotificationViewSet
from presentation.viewsets.product_viewset import ProductViewSet
from presentation.viewsets.report_viewset import ReportViewSet
from presentation.viewsets.sales_viewset import SalesViewSet
from presentation.viewsets.subcategory_viewset import SubCategoryViewSet
from presentation.viewsets.user_viewset import UserViewSet

app_name = "api"

# Create router for ViewSets
router = DefaultRouter()
router.register(r"businesses", BusinessViewSet, basename="business")
router.register(r"dashboard", DashboardViewSet, basename="dashboard")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"inventory", InventoryViewSet, basename="inventory")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"subcategories", SubCategoryViewSet, basename="subcategory")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"sales", SalesViewSet, basename="sales")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"finance", FinanceViewSet, basename="finance")
router.register(r"reports", ReportViewSet, basename="report")
router.register(r"users", UserViewSet, basename="user")

urlpatterns = [
    # Authentication endpoints
    path("auth/signup/", auth_views.signup_view, name="signup"),
    path("auth/login/", auth_views.login_view, name="login"),
    path("auth/verify-otp/", auth_views.verify_otp_view, name="verify-otp"),
    path("auth/request-otp/", auth_views.request_otp_view, name="request-otp"),
    path(
        "auth/google/auth-url/",
        auth_views.google_auth_url_view,
        name="google-auth-url",
    ),
    path(
        "auth/google/callback/",
        auth_views.google_callback_view,
        name="google-callback",
    ),
    path(
        "auth/refresh-token/",
        auth_views.refresh_token_view,
        name="refresh-token",
    ),
    path("auth/logout/", auth_views.logout_view, name="logout"),
    path(
        "auth/forgot-password/",
        auth_views.forgot_password_view,
        name="forgot-password",
    ),
    path(
        "auth/reset-password/",
        auth_views.reset_password_view,
        name="reset-password",
    ),
    path("auth/profile/", auth_views.profile_view, name="profile"),
    path(
        "auth/profile/update/",
        auth_views.update_profile_view,
        name="update-profile",
    ),
    path(
        "auth/sessions/",
        auth_views.user_sessions_view,
        name="user-sessions",
    ),
    # ViewSet routes
    path("", include(router.urls)),
]
