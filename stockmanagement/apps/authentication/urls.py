from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.authentication.views import (
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshTokenView,
    UserCreateView,
    UserInfoView,
    UserManagementViewSet,
    UserUpdateView,
)

router = DefaultRouter()
router.register(r"users", UserManagementViewSet, basename="user")

urlpatterns = [
    path("register/", UserCreateView.as_view(), name="user-register"),
    path("login/", LoginView.as_view(), name="user-login"),
    path("user-info/", UserInfoView.as_view(), name="user-info"),
    path("logout/", LogoutView.as_view(), name="user-logout"),
    path("refresh-token/", RefreshTokenView.as_view(), name="refresh-token"),
    path("update-user/", UserUpdateView.as_view(), name="update-user"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path(
        "password-reset-confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"
    ),
    path("", include(router.urls)),
]
