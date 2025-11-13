"""JWT token blacklist service.

This service handles blacklisting of JWT tokens (access and refresh tokens)
without exposing direct database queries to the use case layer.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

User = get_user_model()


class JWTBlacklistService:
    """Service for managing JWT token blacklist."""

    @staticmethod
    def is_token_blacklisted(jti: str) -> bool:
        """Check if a token is blacklisted by its JTI.

        Args:
            jti: JWT ID (JTI) of the token

        Returns:
            True if token is blacklisted, False otherwise
        """
        try:
            outstanding_token = OutstandingToken.objects.get(jti=jti)
            is_blacklisted: bool = BlacklistedToken.objects.filter(token=outstanding_token).exists()
            return is_blacklisted
        except OutstandingToken.DoesNotExist:
            return False

    @staticmethod
    def blacklist_token(
        jti: str,
        token_string: str,
        user_id: UUID,
        expires_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Blacklist a token by creating or updating OutstandingToken and BlacklistedToken.

        Args:
            jti: JWT ID (JTI) of the token
            token_string: The token string
            user_id: User ID associated with the token
            expires_at: Token expiration time (optional, will be inferred from token if not provided)
            created_at: Token creation time (optional, will use current time if not provided)
        """
        try:
            # Try to get existing OutstandingToken
            outstanding_token = OutstandingToken.objects.get(jti=jti)
        except OutstandingToken.DoesNotExist:
            # Create OutstandingToken if it doesn't exist
            user_model = User.objects.get(id=user_id)
            outstanding_token = OutstandingToken.objects.create(
                jti=jti,
                user=user_model,
                token=token_string,
                created_at=created_at or timezone.now(),
                expires_at=expires_at or (timezone.now() + timezone.timedelta(hours=1)),
            )
            logger.debug(f"Created OutstandingToken for token (jti: {jti})")

        # Blacklist the token
        BlacklistedToken.objects.get_or_create(token=outstanding_token)
        logger.debug(f"Token blacklisted (jti: {jti})")

    @staticmethod
    def blacklist_access_token_by_jti(
        access_token_jti: str,
        user_id: UUID,
        access_token_string: str | None = None,
    ) -> None:
        """Blacklist an access token by its JTI.

        Args:
            access_token_jti: JTI of the access token to blacklist
            user_id: User ID associated with the token
            access_token_string: Optional access token string (for creating OutstandingToken)
        """
        if not access_token_jti:
            logger.warning("Access token JTI is empty, cannot blacklist")
            return

        try:
            # Try to get existing OutstandingToken
            outstanding_token = OutstandingToken.objects.get(jti=access_token_jti)
        except OutstandingToken.DoesNotExist:
            # Create OutstandingToken if it doesn't exist
            # We need to extract expiration from the token string if provided
            if access_token_string:
                try:
                    from rest_framework_simplejwt.tokens import AccessToken as JWTAccessToken

                    access_token = JWTAccessToken(access_token_string)
                    access_exp_timestamp = access_token.get("exp")
                    access_iat_timestamp = access_token.get("iat")
                    access_expires_at = (
                        datetime.fromtimestamp(access_exp_timestamp, tz=UTC)
                        if access_exp_timestamp
                        else timezone.now() + timezone.timedelta(hours=1)
                    )
                    access_created_at = (
                        datetime.fromtimestamp(access_iat_timestamp, tz=UTC)
                        if access_iat_timestamp
                        else timezone.now()
                    )
                except Exception:
                    # Fallback if token parsing fails
                    access_expires_at = timezone.now() + timezone.timedelta(hours=1)
                    access_created_at = timezone.now()
            else:
                # Default expiration if no token string provided
                access_expires_at = timezone.now() + timezone.timedelta(hours=1)
                access_created_at = timezone.now()

            user_model = User.objects.get(id=user_id)
            outstanding_token = OutstandingToken.objects.create(
                jti=access_token_jti,
                user=user_model,
                token=access_token_string or "",
                created_at=access_created_at,
                expires_at=access_expires_at,
            )
            logger.debug(f"Created OutstandingToken for access token (jti: {access_token_jti})")

        # Blacklist the token
        BlacklistedToken.objects.get_or_create(token=outstanding_token)
        logger.debug(f"Access token blacklisted (jti: {access_token_jti})")

    @staticmethod
    def blacklist_access_token_from_refresh_token(
        refresh_token_string: str, user_id: UUID, access_token_jti: str | None = None
    ) -> None:
        """Blacklist the access token associated with a refresh token.

        Args:
            refresh_token_string: The refresh token string
            user_id: User ID associated with the token
            access_token_jti: Optional JTI of the access token (if stored with refresh token)
        """
        # If we have the access token JTI stored, use it directly
        if access_token_jti:
            JWTBlacklistService.blacklist_access_token_by_jti(
                access_token_jti=access_token_jti,
                user_id=user_id,
            )
            return

        # Fallback: try to extract from refresh token (this generates a new token, so not ideal)
        try:
            refresh_token = RefreshToken(refresh_token_string)
            # Note: This creates a NEW access token, not the original one
            # This is why we should store access_token_jti with the refresh token
            access_token = refresh_token.access_token
            access_jti = access_token.get("jti")

            if access_jti:
                JWTBlacklistService.blacklist_access_token_by_jti(
                    access_token_jti=access_jti,
                    user_id=user_id,
                    access_token_string=str(access_token),
                )
        except Exception as e:
            logger.warning(
                f"Failed to blacklist access token from refresh token: {e}", exc_info=True
            )

    @staticmethod
    def blacklist_refresh_token(refresh_token_string: str, user_id: UUID) -> None:
        """Blacklist a refresh token.

        Args:
            refresh_token_string: The refresh token string
            user_id: User ID associated with the token
        """
        try:
            refresh_token = RefreshToken(refresh_token_string)
            refresh_jti = refresh_token.get("jti")

            if not refresh_jti:
                logger.warning("Refresh token has no JTI, cannot blacklist")
                return

            # Extract expiration and creation times from refresh token
            refresh_exp_timestamp = refresh_token.get("exp")
            refresh_iat_timestamp = refresh_token.get("iat")
            refresh_expires_at = (
                datetime.fromtimestamp(refresh_exp_timestamp, tz=UTC)
                if refresh_exp_timestamp
                else timezone.now() + timezone.timedelta(days=30)
            )
            refresh_created_at = (
                datetime.fromtimestamp(refresh_iat_timestamp, tz=UTC)
                if refresh_iat_timestamp
                else timezone.now()
            )

            JWTBlacklistService.blacklist_token(
                jti=refresh_jti,
                token_string=refresh_token_string,
                user_id=user_id,
                expires_at=refresh_expires_at,
                created_at=refresh_created_at,
            )
        except Exception as e:
            logger.warning(f"Failed to blacklist refresh token: {e}", exc_info=True)

    @staticmethod
    def blacklist_all_user_access_tokens(user_id: UUID) -> int:
        """Blacklist all non-expired access tokens for a user.

        This is used during token refresh to invalidate old access tokens.
        Access tokens typically expire in 1 hour, so we blacklist all tokens
        that expire in less than 1 day (to distinguish from refresh tokens).

        Args:
            user_id: User ID

        Returns:
            Number of access tokens blacklisted
        """
        from datetime import timedelta

        # Get all non-expired outstanding tokens for this user
        user_tokens = OutstandingToken.objects.filter(
            user_id=user_id,
            expires_at__gt=timezone.now(),
        )

        blacklisted_count = 0
        for outstanding_token in user_tokens:
            # Check if it's an access token (expires in less than 1 day)
            # Refresh tokens typically expire in 30 days
            token_lifetime = outstanding_token.expires_at - outstanding_token.created_at
            if token_lifetime < timedelta(days=1):
                # Likely an access token - blacklist it
                BlacklistedToken.objects.get_or_create(token=outstanding_token)
                blacklisted_count += 1
                logger.debug(
                    f"Blacklisted access token (jti: {outstanding_token.jti}) "
                    f"for user {user_id}"
                )

        return blacklisted_count

    @staticmethod
    def blacklist_tokens_from_refresh_token(
        refresh_token_string: str, user_id: UUID, access_token_jti: str | None = None
    ) -> None:
        """Blacklist both the refresh token and its associated access token.

        This is used during token refresh to invalidate the old tokens.

        IMPORTANT: Since we can't get the original access token from a refresh token
        (RefreshToken().access_token generates a NEW token), we blacklist ALL
        non-expired access tokens for this user to ensure the old one is invalidated.

        Args:
            refresh_token_string: The refresh token string
            user_id: User ID associated with the token
            access_token_jti: Optional JTI of the access token (if stored with refresh token)
        """
        # If we have the specific access token JTI, use it
        if access_token_jti:
            JWTBlacklistService.blacklist_access_token_by_jti(
                access_token_jti=access_token_jti,
                user_id=user_id,
            )
        else:
            # Blacklist all non-expired access tokens for this user
            # This ensures the old access token is invalidated
            count = JWTBlacklistService.blacklist_all_user_access_tokens(user_id)
            logger.info(f"Blacklisted {count} access token(s) for user {user_id} during refresh")

        # Then blacklist the refresh token
        JWTBlacklistService.blacklist_refresh_token(refresh_token_string, user_id)
