#!/usr/bin/env python
"""Simple script to test API endpoints manually."""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockmanagement.settings")
django.setup()

import requests  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()

BASE_URL = "http://localhost:8000/api/v1"


def print_response(response, title="Response"):
    """Print formatted response."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception:
        print(f"Response: {response.text}")
    print(f"{'='*60}\n")


def test_signup():
    """Test signup endpoint."""
    print("Testing Signup Endpoint...")
    url = f"{BASE_URL}/auth/signup/"
    data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPassword123!",
        "role": "customer",
    }
    response = requests.post(url, json=data)
    print_response(response, "Signup Response")
    return response


def test_login():
    """Test login endpoint."""
    print("Testing Login Endpoint...")
    url = f"{BASE_URL}/auth/login/"
    data = {
        "email": "test@example.com",
        "password": "TestPassword123!",
    }
    response = requests.post(url, json=data)
    print_response(response, "Login Response")
    if response.status_code == 200:
        return response.json()["data"]["access_token"]
    return None


def test_create_business(token):
    """Test create business endpoint."""
    print("Testing Create Business Endpoint...")
    url = f"{BASE_URL}/businesses/"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": "My Supermarket",
        "unique_name": "my-supermarket-123",
        "description": "A test supermarket",
    }
    response = requests.post(url, json=data, headers=headers)
    print_response(response, "Create Business Response")
    if response.status_code == 201:
        return response.json()["data"]["id"]
    return None


if __name__ == "__main__":
    print("Starting API Tests...")
    print(f"Base URL: {BASE_URL}")

    # Test signup
    signup_response = test_signup()

    # Test login (if user was created)
    if signup_response.status_code in [201, 400]:  # 400 if user already exists
        token = test_login()
        if token:
            # Test create business
            business_id = test_create_business(token)
            if business_id:
                print(f"✅ Business created with ID: {business_id}")

    print("\n✅ API Tests Completed!")
