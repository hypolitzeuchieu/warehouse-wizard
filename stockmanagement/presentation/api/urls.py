"""API URL configuration for RetailPulse."""

from django.urls import path

from presentation.views import (
    auth_views,
    business_views,
    inventory_views,
    sales_views,
)

app_name = "api"

urlpatterns = [
    # Authentication endpoints
    path("auth/signup/", auth_views.signup_view, name="signup"),
    path("auth/login/", auth_views.login_view, name="login"),
    path("auth/verify-otp/", auth_views.verify_otp_view, name="verify-otp"),
    path("auth/request-otp/", auth_views.request_otp_view, name="request-otp"),
    path("auth/google/auth-url/", auth_views.google_auth_url_view, name="google-auth-url"),
    path("auth/google/callback/", auth_views.google_callback_view, name="google-callback"),
    path("auth/refresh-token/", auth_views.refresh_token_view, name="refresh-token"),
    path("auth/logout/", auth_views.logout_view, name="logout"),
    path("auth/forgot-password/", auth_views.forgot_password_view, name="forgot-password"),
    path("auth/reset-password/", auth_views.reset_password_view, name="reset-password"),
    path("auth/profile/", auth_views.profile_view, name="profile"),
    path("auth/profile/update/", auth_views.update_profile_view, name="update-profile"),
    path("auth/sessions/", auth_views.user_sessions_view, name="user-sessions"),
    # Business endpoints
    path("businesses/", business_views.create_business_view, name="create-business"),
    path(
        "businesses/<uuid:business_id>/",
        business_views.update_business_view,
        name="update-business",
    ),
    path(
        "businesses/<uuid:business_id>/delete/",
        business_views.delete_business_view,
        name="delete-business",
    ),
    path(
        "businesses/<uuid:business_id>/members/",
        business_views.add_business_member_view,
        name="add-business-member",
    ),
    path(
        "businesses/<uuid:business_id>/members/<uuid:member_id>/",
        business_views.remove_business_member_view,
        name="remove-business-member",
    ),
    # Inventory endpoints
    path(
        "businesses/<uuid:business_id>/products/",
        inventory_views.create_product_view,
        name="create-product",
    ),
    path(
        "businesses/<uuid:business_id>/stock-movements/",
        inventory_views.record_stock_movement_view,
        name="record-stock-movement",
    ),
    path(
        "businesses/<uuid:business_id>/products/low-stock/",
        inventory_views.get_low_stock_products_view,
        name="low-stock-products",
    ),
    path(
        "businesses/<uuid:business_id>/products/expired/",
        inventory_views.get_expired_products_view,
        name="expired-products",
    ),
    # Sales endpoints (POS)
    path(
        "businesses/<uuid:business_id>/invoices/",
        sales_views.create_invoice_view,
        name="create-invoice",
    ),
    path(
        "businesses/<uuid:business_id>/invoices/<uuid:invoice_id>/",
        sales_views.get_invoice_view,
        name="get-invoice",
    ),
]
