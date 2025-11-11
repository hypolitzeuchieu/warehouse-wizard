"""Google OAuth use case."""

from __future__ import annotations

import logging
from typing import Callable
from uuid import uuid4

from application.dto.user_dto import (
    GoogleOAuthAuthURLDTO,
    GoogleOAuthAuthURLResponseDTO,
    GoogleOAuthCodeDTO,
    GoogleOAuthDTO,
    LoginResponseDTO,
    UserResponseDTO,
)
from domain.users.entities import AuthMethod, Device, User, UserRole
from domain.users.repositories import DeviceRepository, UserRepository
from domain.users.services import UserDomainService
from django.utils import timezone
from infrastructure.external.google_oauth import GoogleOAuthService
from infrastructure.persistence.repositories import (
    DeviceRepositoryImpl,
    RefreshTokenRepositoryImpl,
    SessionRepositoryImpl,
)
from shared.exceptions.base import BaseAPIException

logger = logging.getLogger(__name__)


class GoogleOAuthAuthURLUseCase:
    """Use case for generating Google OAuth authorization URL."""

    def __init__(self, google_oauth_service: GoogleOAuthService):
        """Initialize use case."""
        self.google_oauth_service = google_oauth_service

    def execute(self) -> GoogleOAuthAuthURLResponseDTO:
        """
        Generate Google OAuth authorization URL.
        
        Note: Purpose (signup/login) is auto-detected during callback based on whether user exists.

        Returns:
            GoogleOAuthAuthURLResponseDTO with auth URL

        Raises:
            ValueError: If Google OAuth is not configured
        """
        if not self.google_oauth_service.is_configured():
            raise ValueError("Google OAuth is not configured")

        result = self.google_oauth_service.generate_auth_url()

        return GoogleOAuthAuthURLResponseDTO(
            auth_url=result["auth_url"],
            expires_in=result["expires_in"],
        )


class GoogleOAuthCodeUseCase:
    """Use case for Google OAuth code exchange and authentication."""

    def __init__(
        self,
        user_repository: UserRepository,
        user_domain_service: UserDomainService,
        session_repository: SessionRepositoryImpl,
        device_repository: DeviceRepository,
        google_oauth_service: GoogleOAuthService,
    ):
        """Initialize use case."""
        self.user_repository = user_repository
        self.user_domain_service = user_domain_service
        self.session_repository = session_repository
        self.device_repository = device_repository
        self.google_oauth_service = google_oauth_service

    def execute(
        self, dto: GoogleOAuthCodeDTO, generate_tokens_func: Callable
    ) -> LoginResponseDTO:
        """
        Exchange Google OAuth code for tokens and authenticate user.

        Args:
            dto: Google OAuth code DTO
            generate_tokens_func: Function to generate JWT tokens

        Returns:
            LoginResponseDTO with tokens and user info

        Raises:
            BaseAPIException: If code exchange fails or user creation/login fails
        """
        # Exchange code for token and get user info
        google_data = self.google_oauth_service.exchange_code_for_token(code=dto.code)

        if not google_data:
            raise BaseAPIException(
                detail="Failed to exchange Google OAuth code",
                code="GOOGLE_OAUTH_EXCHANGE_FAILED",
                status_code=401,
            )

        email = google_data.get("email")
        if not email:
            raise BaseAPIException(
                detail="Email not provided by Google",
                code="GOOGLE_EMAIL_MISSING",
                status_code=400,
            )

        # Check if email is verified
        if not google_data.get("verified_email", False):
            raise BaseAPIException(
                detail="Google email is not verified",
                code="GOOGLE_EMAIL_NOT_VERIFIED",
                status_code=400,
            )

        avatar_url = google_data.get("picture")

        # Check if user exists
        user = self.user_repository.get_by_email(email)

        if not user:
            # Auto-detect: User doesn't exist, so this is a signup flow
            logger.info(f"Google OAuth signup detected for email: {email}")

            # Generate name from email (name is not unique)
            name = email.split("@")[0]

            # Create new user from Google info
            user = User(
                id=uuid4(),
                email=email,
                name=name,
                phone_number=None,
                role=UserRole.CUSTOMER,  # Default role, can be changed when creating business
                is_active=True,  # Google verified users are active
                is_staff=False,
                is_superuser=False,
                last_login=None,
                address=None,
                avatar_url=avatar_url,  # Set Google avatar
                created_at=timezone.now(),
                updated_at=timezone.now(),
                auth_method=AuthMethod.GOOGLE_OAUTH,  # Mark as Google OAuth signup
            )
            user = self.user_repository.create(user)
        else:
            # Auto-detect: User exists, so this is a login flow
            logger.info(f"Google OAuth login detected for email: {email}")

            # Security: Check if user registered with Google OAuth
            if user.auth_method != AuthMethod.GOOGLE_OAUTH:
                raise BaseAPIException(
                    detail=f"Account was created with {user.auth_method.value}. Please use the original authentication method to login.",
                    code="AUTH_METHOD_MISMATCH",
                    status_code=400,
                )

            # Security: Ensure email consistency
            if user.email and user.email.lower() != email.lower():
                raise BaseAPIException(
                    detail="Email mismatch. Please use the email you signed up with.",
                    code="EMAIL_MISMATCH",
                    status_code=400,
                )

            # Update avatar if provided and different
            if avatar_url and user.avatar_url != avatar_url:
                user.avatar_url = avatar_url
                user = self.user_repository.update(user)

            # Ensure user is active
            if not user.is_active:
                user.is_active = True
                user = self.user_repository.update(user)

        # Create or update device if device_id provided
        if dto.device_id:
            existing_device = self.device_repository.get_by_device_id(dto.device_id)
            if existing_device:
                # Update existing device
                existing_device.last_used_at = timezone.now()
                if dto.device_name:
                    existing_device.device_name = dto.device_name
                if dto.device_type:
                    existing_device.device_type = dto.device_type
                if dto.ip_address:
                    existing_device.ip_address = dto.ip_address
                if dto.user_agent:
                    existing_device.user_agent = dto.user_agent
                existing_device.updated_at = timezone.now()
                self.device_repository.update(existing_device)
            else:
                # Create new device
                device = Device(
                    id=uuid4(),
                    user_id=user.id,
                    device_id=dto.device_id,
                    device_name=dto.device_name,
                    device_type=dto.device_type,
                    ip_address=dto.ip_address,
                    user_agent=dto.user_agent,
                    last_used_at=timezone.now(),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                self.device_repository.create(device)

        # Create session
        session = self.user_domain_service.start_session(
            user_id=user.id,
            device_id=dto.device_id,
            ip_address=dto.ip_address,
            user_agent=dto.user_agent,
        )

        # Generate tokens
        tokens = generate_tokens_func(user)

        # Store refresh token
        self.user_domain_service.create_refresh_token(
            user_id=user.id,
            token=tokens["refresh"],
            device_id=dto.device_id,
            ip_address=dto.ip_address,
        )

        # Update last login
        user.last_login = timezone.now()
        user = self.user_repository.update(user)

        return LoginResponseDTO(
            access_token=tokens["access"],
            refresh_token=tokens["refresh"],
            user=UserResponseDTO(
                id=user.id,
                email=user.email or "",
                name=user.name,
                phone_number=user.phone_number,
                role=user.role.value if isinstance(user.role, UserRole) else user.role,
                is_active=user.is_active,
                is_staff=user.is_staff,
                is_superuser=user.is_superuser,
                last_login=user.last_login,
                address=user.address,
                avatar_url=user.avatar_url,
                created_at=user.created_at,
                updated_at=user.updated_at,
            ),
            expires_in=tokens.get("expires_in", 3600),
        )


class GoogleOAuthUseCase:
    """Use case for Google OAuth authentication (legacy - for backward compatibility)."""

    def __init__(
        self,
        user_repository: UserRepository,
        user_domain_service: UserDomainService,
        session_repository: SessionRepositoryImpl,
        device_repository: DeviceRepository,
        google_oauth_service: GoogleOAuthService,
    ):
        """Initialize use case."""
        self.user_repository = user_repository
        self.user_domain_service = user_domain_service
        self.session_repository = session_repository
        self.device_repository = device_repository
        self.google_oauth_service = google_oauth_service

    def execute(
        self, dto: GoogleOAuthDTO, generate_tokens_func: Callable
    ) -> LoginResponseDTO:
        """
        Execute Google OAuth authentication (legacy method).

        Args:
            dto: Google OAuth DTO
            generate_tokens_func: Function to generate JWT tokens

        Returns:
            LoginResponseDTO with tokens and user info

        Raises:
            ValueError: If token is invalid
            Exception: If user creation/login fails
        """
        # This is legacy - we should use GoogleOAuthCodeUseCase instead
        # But keeping for backward compatibility
        raise BaseAPIException(
            detail="This endpoint is deprecated. Please use /auth/google/auth-url and /auth/google/callback",
            code="DEPRECATED_ENDPOINT",
            status_code=410,
        )
