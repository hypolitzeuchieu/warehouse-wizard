"""Google OAuth service implementation."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """Service for Google OAuth authentication."""

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    @staticmethod
    def generate_auth_url() -> str:
        """
        Generate Google OAuth authorization URL.
        Note: Purpose (signup/login) is auto-detected based on whether user exists.

        Returns:
            Dictionary with auth_url
        """

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }

        auth_url = f"{GoogleOAuthService.GOOGLE_AUTH_URL}?{urlencode(params)}"

        return auth_url

    @staticmethod
    def exchange_code_for_token(code: str) -> dict | None:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from Google (must be URL-decoded if needed)

        Returns:
            Dictionary with access_token, refresh_token, and user info, or None if invalid
        """
        try:
            # Clean and validate code
            code = code.strip()
            if not code:
                logger.error("Empty authorization code")
                return None

            # Exchange code for token
            token_response = requests.post(
                GoogleOAuthService.GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )

            if token_response.status_code != 200:
                error_data = token_response.json() if token_response.text else {}
                logger.error(
                    f"Token exchange failed: {error_data.get('error', 'Unknown error')} - "
                    f"{error_data.get('error_description', token_response.text)}"
                )
                return None

            token_data = token_response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")

            if not access_token:
                logger.error("No access token in response")
                return None

            # Get user info from Google
            userinfo_response = requests.get(
                GoogleOAuthService.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )

            if userinfo_response.status_code != 200:
                logger.error(f"User info fetch failed: {userinfo_response.text}")
                return None

            user_info = userinfo_response.json()

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": token_data.get("expires_in", 3600),
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "given_name": user_info.get("given_name"),
                "family_name": user_info.get("family_name"),
                "picture": user_info.get("picture"),
                "sub": user_info.get("id"),
                "verified_email": user_info.get("verified_email", False),
            }
        except requests.RequestException as e:
            logger.error(f"Request error during token exchange: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during token exchange: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def is_configured() -> bool:
        """Check if Google OAuth is configured."""
        return all(
            [
                hasattr(settings, "GOOGLE_CLIENT_ID") and settings.GOOGLE_CLIENT_ID,
                hasattr(settings, "GOOGLE_CLIENT_SECRET") and settings.GOOGLE_CLIENT_SECRET,
                hasattr(settings, "GOOGLE_REDIRECT_URI") and settings.GOOGLE_REDIRECT_URI,
            ]
        )
