from django.urls import path

from authentication.views import (
    RegisterWholesaleClientView,
    UserCreateView,
    LoginView,
    LogoutView
)


urlpatterns = [
    path('register/', UserCreateView.as_view(), name='user-register'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('register-wholesale-client/', RegisterWholesaleClientView.as_view(), name='register-wholesale-client'),
]
