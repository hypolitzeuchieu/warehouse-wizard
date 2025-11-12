"""Tests for business endpoints."""

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
def authenticated_user(api_client):
    """Create and authenticate a user."""
    user_data = {
        "email": f"owner_{uuid4().hex[:8]}@example.com",
        "username": f"owner_{uuid4().hex[:8]}",
        "password": "TestPassword123!",
        "role": "owner",
    }

    # Signup
    signup_url = reverse("api:signup")
    api_client.post(signup_url, data=user_data, format="json")

    # Activate and set password
    user = User.objects.get(email=user_data["email"])
    user.is_active = True
    user.set_password(user_data["password"])
    user.save()

    # Login
    login_url = reverse("api:login")
    login_response = api_client.post(
        login_url,
        data={"email": user_data["email"], "password": user_data["password"]},
        format="json",
    )
    access_token = login_response.data["data"]["access_token"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    return user


@pytest.mark.django_db
class TestBusinessEndpoints:
    """Test business endpoints."""

    def test_create_business_success(self, api_client, authenticated_user):
        """Test successful business creation."""
        url = reverse("api:create-business")
        business_data = {
            "name": "Test Supermarket",
            "unique_name": f"test-market-{uuid4().hex[:8]}",
            "description": "A test supermarket",
            "address": "123 Test Street",
            "phone_number": "+1234567890",
            "email": "market@example.com",
        }
        response = api_client.post(url, data=business_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] is True
        assert "Business created successfully" in response.data["message"]
        assert "data" in response.data
        assert response.data["data"]["name"] == business_data["name"]
        assert response.data["data"]["unique_name"] == business_data["unique_name"]

    def test_create_business_duplicate_unique_name(self, api_client, authenticated_user):
        """Test business creation with duplicate unique name."""
        url = reverse("api:create-business")
        business_data = {
            "name": "Test Supermarket",
            "unique_name": f"test-market-{uuid4().hex[:8]}",
        }

        # Create first business
        api_client.post(url, data=business_data, format="json")

        # Try to create second with same unique_name
        business_data["name"] = "Another Market"
        response = api_client.post(url, data=business_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "unique name" in response.data["error"]["message"].lower()

    def test_create_business_unauthenticated(self, api_client):
        """Test business creation without authentication."""
        url = reverse("api:create-business")
        business_data = {
            "name": "Test Supermarket",
            "unique_name": f"test-market-{uuid4().hex[:8]}",
        }
        response = api_client.post(url, data=business_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_business_success(self, api_client, authenticated_user):
        """Test successful business update."""
        # Create business first
        create_url = reverse("api:create-business")
        business_data = {
            "name": "Test Supermarket",
            "unique_name": f"test-market-{uuid4().hex[:8]}",
        }
        create_response = api_client.post(create_url, data=business_data, format="json")
        business_id = create_response.data["data"]["id"]

        # Update business
        update_url = reverse("api:update-business", args=[business_id])
        update_data = {
            "name": "Updated Supermarket",
            "description": "Updated description",
        }
        response = api_client.put(update_url, data=update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert response.data["data"]["name"] == "Updated Supermarket"

    def test_delete_business_success(self, api_client, authenticated_user):
        """Test successful business deletion."""
        # Create business first
        create_url = reverse("api:create-business")
        business_data = {
            "name": "Test Supermarket",
            "unique_name": f"test-market-{uuid4().hex[:8]}",
        }
        create_response = api_client.post(create_url, data=business_data, format="json")
        business_id = create_response.data["data"]["id"]

        # Delete business
        delete_url = reverse("api:delete-business", args=[business_id])
        response = api_client.delete(delete_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert "deleted successfully" in response.data["message"].lower()
