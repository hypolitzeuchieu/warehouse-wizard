from __future__ import annotations

from authentication.views import LoginView
from authentication.views import LogoutView
from authentication.views import PasswordResetConfirmView
from authentication.views import PasswordResetRequestView
from authentication.views import UserCreateView
from authentication.views import UserManagementViewSet
from authentication.views import UserUpdateView
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', UserManagementViewSet, basename='user')

urlpatterns = [
    path('register/', UserCreateView.as_view(), name='user-register'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
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
