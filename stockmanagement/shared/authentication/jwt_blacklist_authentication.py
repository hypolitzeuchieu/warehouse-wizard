"""Custom JWT authentication with blacklist checking."""

from __future__ import annotations

import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

logger = logging.getLogger(__name__)


class JWTAuthenticationWithBlacklist(JWTAuthentication):
    """
    Custom JWT authentication that checks token blacklist.

    This ensures that blacklisted tokens (from logout) are rejected.
    """

    def authenticate(self, request):
        """
        Authenticate the request and check if token is blacklisted.

        Returns:
            tuple: (user, token) if authentication successful, None otherwise

        Raises:
            InvalidToken: If token is blacklisted or invalid
        """
        # First, try the standard JWT authentication
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)

        # Check if token is blacklisted
        jti = validated_token.get("jti")
        if jti:
            try:
                # Check if token is in blacklist
                outstanding_token = OutstandingToken.objects.get(jti=jti)
                if BlacklistedToken.objects.filter(token=outstanding_token).exists():
                    # This is expected behavior after logout - log at INFO level, not WARNING
                    user_id = validated_token.get("user_id")
                    logger.info(
                        f"Blacklisted token rejected - jti: {jti[:16]}..., user_id: {user_id}"
                    )
                    raise InvalidToken("Token has been blacklisted (logged out)")
            except OutstandingToken.DoesNotExist:
                # Token not in outstanding tokens, might be a new token
                # This is OK, continue with authentication
                pass
            except InvalidToken:
                # Re-raise InvalidToken (blacklisted)
                raise
            except Exception as e:
                # Log error but don't fail authentication for other errors
                # Use warning level but without full traceback for expected errors
                logger.warning(
                    f"Error checking token blacklist: {type(e).__name__}: {str(e)}",
                    extra={"jti": jti},
                )

        return self.get_user(validated_token), validated_token
