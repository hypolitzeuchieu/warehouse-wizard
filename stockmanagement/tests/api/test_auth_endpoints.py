"""Tests for authentication endpoints."""

from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "email": f"test_{uuid4().hex[:8]}@example.com",
        "username": f"testuser_{uuid4().hex[:8]}",
        "password": "TestPassword123!",
        "phone_number": "+1234567890",
        "role": "customer",
    }


@pytest.mark.django_db
class TestSignupEndpoint:
    """Test signup endpoint."""

    def test_signup_success(self, api_client, test_user_data):
        """Test successful user signup."""
        url = reverse("api:signup")
        response = api_client.post(url, data=test_user_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] is True
        assert "User created successfully" in response.data["message"]
        assert "user" in response.data["data"]
        assert response.data["data"]["user"]["email"] == test_user_data["email"]

    def test_signup_duplicate_email(self, api_client, test_user_data):
        """Test signup with duplicate email."""
        # Create first user
        url = reverse("api:signup")
        api_client.post(url, data=test_user_data, format="json")

        # Try to create second user with same email
        test_user_data["username"] = f"another_{uuid4().hex[:8]}"
        response = api_client.post(url, data=test_user_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "already exists" in response.data["error"]["message"].lower()

    def test_signup_manager_role_forbidden(self, api_client, test_user_data):
        """Test that users cannot signup with manager role."""
        test_user_data["role"] = "manager"
        url = reverse("api:signup")
        response = api_client.post(url, data=test_user_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "manager" in response.data["error"]["message"].lower()

    def test_signup_validation_error(self, api_client):
        """Test signup with invalid data."""
        url = reverse("api:signup")
        invalid_data = {"email": "invalid-email"}
        response = api_client.post(url, data=invalid_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data


@pytest.mark.django_db
class TestLoginEndpoint:
    """Test login endpoint."""

    def test_login_success(self, api_client, test_user_data):
        """Test successful login."""
        # First, create a user
        signup_url = reverse("api:signup")
        signup_response = api_client.post(signup_url, data=test_user_data, format="json")
        assert signup_response.status_code == status.HTTP_201_CREATED

        # Activate user (in real scenario, this would be done via OTP)
        user = User.objects.get(email=test_user_data["email"])
        user.is_active = True
        user.set_password(test_user_data["password"])
        user.save()

        # Now try to login
        login_url = reverse("api:login")
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        response = api_client.post(login_url, data=login_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert "access_token" in response.data["data"]
        assert "refresh_token" in response.data["data"]
        assert "user" in response.data["data"]

    def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials."""
        url = reverse("api:login")
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword",
        }
        response = api_client.post(url, data=login_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data
        assert "invalid" in response.data["error"]["message"].lower()

    def test_login_inactive_user(self, api_client, test_user_data):
        """Test login with inactive user."""
        # Create user but don't activate
        signup_url = reverse("api:signup")
        api_client.post(signup_url, data=test_user_data, format="json")

        user = User.objects.get(email=test_user_data["email"])
        user.set_password(test_user_data["password"])
        user.save()  # is_active is False by default

        login_url = reverse("api:login")
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        response = api_client.post(login_url, data=login_data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "error" in response.data
        assert "inactive" in response.data["error"]["message"].lower()


@pytest.mark.django_db
class TestRefreshTokenEndpoint:
    """Test refresh token endpoint."""

    def test_refresh_token_success(self, api_client, test_user_data):
        """Test successful token refresh."""
        # Create and login user
        signup_url = reverse("api:signup")
        api_client.post(signup_url, data=test_user_data, format="json")

        user = User.objects.get(email=test_user_data["email"])
        user.is_active = True
        user.set_password(test_user_data["password"])
        user.save()

        login_url = reverse("api:login")
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        login_response = api_client.post(login_url, data=login_data, format="json")
        refresh_token = login_response.data["data"]["refresh_token"]

        # Refresh token
        refresh_url = reverse("api:refresh-token")
        refresh_data = {"refresh_token": refresh_token}
        response = api_client.post(refresh_url, data=refresh_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert "access_token" in response.data["data"]
        assert "refresh_token" in response.data["data"]

    def test_refresh_token_invalid(self, api_client):
        """Test refresh with invalid token."""
        url = reverse("api:refresh-token")
        refresh_data = {"refresh_token": "invalid_token"}
        response = api_client.post(url, data=refresh_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data


@pytest.mark.django_db
class TestLogoutEndpoint:
    """Test logout endpoint."""

    def test_logout_success(self, api_client, test_user_data):
        """Test successful logout."""
        # Create, activate and login user
        signup_url = reverse("api:signup")
        api_client.post(signup_url, data=test_user_data, format="json")

        user = User.objects.get(email=test_user_data["email"])
        user.is_active = True
        user.set_password(test_user_data["password"])
        user.save()

        login_url = reverse("api:login")
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        login_response = api_client.post(login_url, data=login_data, format="json")
        access_token = login_response.data["data"]["access_token"]

        # Logout
        logout_url = reverse("api:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = api_client.post(logout_url, data={}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert "Logout successful" in response.data["message"]
