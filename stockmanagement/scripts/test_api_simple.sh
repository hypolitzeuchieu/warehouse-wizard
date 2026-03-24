#!/bin/bash
# Simple script to test API endpoints using curl

BASE_URL="http://localhost:8000/api/v1"

echo "============================================================"
echo "RetailPulse API Endpoint Tests"
echo "============================================================"
echo ""

# Test 1: Signup
echo "Test 1: Signup Endpoint"
echo "----------------------"
SIGNUP_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/signup/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test'$(date +%s)'@example.com",
    "username": "testuser'$(date +%s)'",
    "password": "TestPassword123!",
    "role": "customer"
  }')

echo "$SIGNUP_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SIGNUP_RESPONSE"
echo ""

# Extract email from response if successful
EMAIL=$(echo "$SIGNUP_RESPONSE" | grep -o '"email":"[^"]*"' | cut -d'"' -f4 | head -1)

if [ -z "$EMAIL" ]; then
  echo "❌ Signup failed or user already exists"
  echo ""
  exit 1
fi

echo "✅ Signup successful - Email: $EMAIL"
echo ""

# Test 2: Login (requires user to be activated first)
echo "Test 2: Login Endpoint"
echo "----------------------"
echo "Note: User must be activated in database first"
echo ""

# Test 3: API Documentation
echo "Test 3: API Documentation Endpoint"
echo "-----------------------------------"
DOC_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/docs/")
if [ "$DOC_RESPONSE" = "200" ] || [ "$DOC_RESPONSE" = "401" ]; then
  echo "✅ Documentation endpoint accessible (Status: $DOC_RESPONSE)"
else
  echo "❌ Documentation endpoint not accessible (Status: $DOC_RESPONSE)"
fi
echo ""

echo "============================================================"
echo "Tests Completed!"
echo "============================================================"
echo ""
echo "To test login, you need to:"
echo "1. Activate the user in the database"
echo "2. Run: python manage.py shell"
echo "3. Execute:"
echo "   from infrastructure.persistence.models.user_models import User"
echo "   user = User.objects.get(email='$EMAIL')"
echo "   user.is_active = True"
echo "   user.set_password('TestPassword123!')"
echo "   user.save()"
echo ""

