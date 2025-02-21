from __future__ import annotations

from authentication.views import LoginView
from authentication.views import LogoutView
from authentication.views import UserCreateView
from authentication.views import UserManagementViewSet
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', UserManagementViewSet, basename='user')

urlpatterns = [
    path('register/', UserCreateView.as_view(), name='user-register'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('', include(router.urls)),
]
