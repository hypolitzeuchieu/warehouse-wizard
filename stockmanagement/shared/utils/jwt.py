"""JWT utility functions."""

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def generate_tokens(user: Any) -> dict[str, str]:
    """Generate access and refresh tokens for a user.

    Args:
        user: User instance (can be domain entity or Django model)

    Returns:
        Dictionary with 'access' and 'refresh' tokens
    """
    # If user is a domain entity, get the Django model
    if hasattr(user, "id") and not hasattr(user, "pk"):
        # It's a domain entity, get Django model
        user_model = User.objects.get(id=user.id)
    else:
        # It's already a Django model
        user_model = user

    refresh = RefreshToken.for_user(user_model)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

