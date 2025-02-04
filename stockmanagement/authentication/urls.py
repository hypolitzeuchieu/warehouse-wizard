from __future__ import annotations

from authentication.views import LoginView
from authentication.views import LogoutView
from authentication.views import RegisterUserView
from authentication.views import UserCreateView
from django.urls import path


urlpatterns = [
    path('register/', UserCreateView.as_view(), name='user-register'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path(
        'register-whole-client-sales-agent/',
        RegisterUserView.as_view(),
        name='register-client-sales-agent',
    ),
]
