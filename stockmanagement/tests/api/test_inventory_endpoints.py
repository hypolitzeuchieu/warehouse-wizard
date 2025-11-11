"""Tests for inventory endpoints."""

import json
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.inventory_models import Category

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def business_and_user(api_client):
    """Create a business and authenticated user."""
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

    # Create business
    business_url = reverse("api:create-business")
    business_data = {
        "name": "Test Supermarket",
        "unique_name": f"test-market-{uuid4().hex[:8]}",
    }
    business_response = api_client.post(
        business_url, data=business_data, format="json"
    )
    business_id = business_response.data["data"]["id"]

    business = Business.objects.get(id=business_id)

    return user, business


@pytest.mark.django_db
class TestProductEndpoints:
    """Test product endpoints."""

    def test_create_product_success(self, api_client, business_and_user):
        """Test successful product creation."""
        user, business = business_and_user

        # Create category first
        category = Category.objects.create(
            business=business,
            name="Electronics",
            description="Electronic products",
        )

        url = reverse("api:create-product", args=[business.id])
        product_data = {
            "name": "Test Product",
            "category_id": str(category.id),
            "purchase_price": "10.00",
            "unit_price": "15.00",
            "quantity": 100,
            "min_quantity": 10,
        }
        response = api_client.post(url, data=product_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] is True
        assert "Product created successfully" in response.data["message"]
        assert response.data["data"]["name"] == "Test Product"

    def test_create_product_invalid_category(
        self, api_client, business_and_user
    ):
        """Test product creation with invalid category."""
        user, business = business_and_user

        url = reverse("api:create-product", args=[business.id])
        product_data = {
            "name": "Test Product",
            "category_id": str(uuid4()),  # Non-existent category
            "purchase_price": "10.00",
            "unit_price": "15.00",
        }
        response = api_client.post(url, data=product_data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.data
        assert "category" in response.data["error"]["message"].lower()

    def test_get_low_stock_products(
        self, api_client, business_and_user
    ):
        """Test getting low stock products."""
        user, business = business_and_user

        url = reverse("api:low-stock-products", args=[business.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert "data" in response.data
        assert isinstance(response.data["data"], list)

    def test_get_expired_products(self, api_client, business_and_user):
        """Test getting expired products."""
        user, business = business_and_user

        url = reverse("api:expired-products", args=[business.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert "data" in response.data
        assert isinstance(response.data["data"], list)

