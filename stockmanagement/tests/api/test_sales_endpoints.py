"""Tests for sales (POS) endpoints."""

from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.inventory_models import Category, Product

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def business_with_product(api_client):
    """Create a business, user, and product."""
    user_data = {
        "email": f"cashier_{uuid4().hex[:8]}@example.com",
        "username": f"cashier_{uuid4().hex[:8]}",
        "password": "TestPassword123!",
        "role": "cashier",
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
    business_response = api_client.post(business_url, data=business_data, format="json")
    business_id = business_response.data["data"]["id"]
    business = Business.objects.get(id=business_id)

    # Create category and product
    category = Category.objects.create(business=business, name="Food", description="Food items")
    product = Product.objects.create(
        business=business,
        category=category,
        name="Test Product",
        purchase_price=10.00,
        unit_price=15.00,
        quantity=100,
        min_quantity=10,
    )

    return user, business, product


@pytest.mark.django_db
class TestInvoiceEndpoints:
    """Test invoice (POS) endpoints."""

    def test_create_invoice_success(self, api_client, business_with_product):
        """Test successful invoice creation."""
        user, business, product = business_with_product

        url = reverse("api:create-invoice", args=[business.id])
        invoice_data = {
            "customer_name": "John Doe",
            "lines": [
                {
                    "product_id": str(product.id),
                    "quantity": 2,
                    "unit_price": "15.00",
                    "discount": "0.00",
                }
            ],
            "tax": "0.00",
            "discount": "0.00",
            "payment_method": "cash",
        }
        response = api_client.post(url, data=invoice_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] is True
        assert "Invoice created successfully" in response.data["message"]
        assert "data" in response.data
        assert "number" in response.data["data"]
        assert "total" in response.data["data"]
        assert len(response.data["data"]["lines"]) == 1

        # Verify stock was updated
        product.refresh_from_db()
        assert product.quantity == 98  # 100 - 2

    def test_create_invoice_insufficient_stock(self, api_client, business_with_product):
        """Test invoice creation with insufficient stock."""
        user, business, product = business_with_product

        url = reverse("api:create-invoice", args=[business.id])
        invoice_data = {
            "customer_name": "John Doe",
            "lines": [
                {
                    "product_id": str(product.id),
                    "quantity": 200,  # More than available (100)
                    "unit_price": "15.00",
                    "discount": "0.00",
                }
            ],
            "payment_method": "cash",
        }
        response = api_client.post(url, data=invoice_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "insufficient" in response.data["error"]["message"].lower()

    def test_get_invoice_success(self, api_client, business_with_product):
        """Test getting an invoice."""
        user, business, product = business_with_product

        # Create invoice first
        create_url = reverse("api:create-invoice", args=[business.id])
        invoice_data = {
            "customer_name": "John Doe",
            "lines": [
                {
                    "product_id": str(product.id),
                    "quantity": 1,
                    "unit_price": "15.00",
                    "discount": "0.00",
                }
            ],
            "payment_method": "cash",
        }
        create_response = api_client.post(create_url, data=invoice_data, format="json")
        invoice_id = create_response.data["data"]["id"]

        # Get invoice
        get_url = reverse("api:get-invoice", args=[business.id, invoice_id])
        response = api_client.get(get_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] is True
        assert response.data["data"]["id"] == invoice_id
        assert len(response.data["data"]["lines"]) == 1
