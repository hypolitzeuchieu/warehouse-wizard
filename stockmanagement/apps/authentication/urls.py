from __future__ import annotations

from apps.authentication.views import LoginView
from apps.authentication.views import LogoutView
from apps.authentication.views import PasswordResetConfirmView
from apps.authentication.views import PasswordResetRequestView
from apps.authentication.views import RefreshTokenView
from apps.authentication.views import UserCreateView
from apps.authentication.views import UserInfoView
from apps.authentication.views import UserManagementViewSet
from apps.authentication.views import UserUpdateView
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', UserManagementViewSet, basename='user')

urlpatterns = [
    path('register/', UserCreateView.as_view(), name='user-register'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('user-info/', UserInfoView.as_view(), name='user-info'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('refresh-token/', RefreshTokenView.as_view(), name='refresh-token'),
    path('update-user/', UserUpdateView.as_view(), name='update-user'),
    path('password-reset/',
         PasswordResetRequestView.as_view(),
         name='password-reset-request'
         ),
    path('password-reset-confirm/',
         PasswordResetConfirmView.as_view(),
         name='password-reset-confirm'
         ),

    path('', include(router.urls)),
]
