"""JWT utility functions."""

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def generate_tokens(user: Any) -> dict[str, str | None]:
    """Generate access and refresh tokens for a user.

    Args:
        user: User instance (can be domain entity or Django model)

    Returns:
        Dictionary with 'access', 'refresh' tokens and 'access_token_jti'
    """
    # If user is a domain entity, get the Django model
    if hasattr(user, "id") and not hasattr(user, "pk"):
        # It's a domain entity, get Django model
        user_model = User.objects.get(id=user.id)
    else:
        # It's already a Django model
        user_model = user

    refresh = RefreshToken.for_user(user_model)
    access_token = refresh.access_token
    access_token_jti = access_token.get("jti") if access_token else None

    return {
        "access": str(access_token),
        "refresh": str(refresh),
        "access_token_jti": access_token_jti,
    }
