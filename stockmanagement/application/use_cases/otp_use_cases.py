"""OTP use cases."""

from __future__ import annotations

import logging
from collections.abc import Callable

from application.dto.user_dto import (
    LoginResponseDTO,
    OTPRequestDTO,
    OTPVerifyDTO,
    UserResponseDTO,
)
from domain.users.entities import UserRole
from domain.users.repositories import (
    DeviceRepository,
    OTPRepository,
    SessionRepository,
    UserRepository,
)
from domain.users.services import UserDomainService
from shared.exceptions.base import BaseAPIException
from shared.services.otp_service import OTPService

logger = logging.getLogger(__name__)


class RequestOTPUseCase:
    """Use case for requesting an OTP."""

    def __init__(
        self,
        otp_repository: OTPRepository,
        user_repository: UserRepository,
    ):
        """Initialize use case."""
        self.otp_repository = otp_repository
        self.user_repository = user_repository

    def execute(self, dto: OTPRequestDTO) -> dict:
        """
        Execute OTP request.

        Args:
            dto: OTP request DTO

        Returns:
            Dictionary with success message

        Raises:
            BaseAPIException: If user not found or OTP sending fails
        """
        user = None
        if dto.email:
            user = self.user_repository.get_by_email(dto.email)
        # TODO: Add get_by_phone_number to UserRepository if needed for phone-based lookup

        if user and dto.email and user.email and user.email.lower() != dto.email.lower():
            raise BaseAPIException(
                detail="Email does not match user account",
                code="EMAIL_MISMATCH",
                status_code=400,
            )

        # Create OTP (no need for purpose - simplified flow)
        otp = OTPService.create_otp(
            otp_repository=self.otp_repository,
            user_id=user.id if user else None,
            email=dto.email,
            phone_number=dto.phone_number,
            otp_type=dto.otp_type,
        )

        # Send OTP asynchronously via Celery
        if dto.otp_type == "email" and dto.email:
            from kombu.exceptions import OperationalError

            from tasks.otp_tasks import send_otp_email_task

            try:
                # Send email in background
                send_otp_email_task.delay(
                    email=dto.email,
                    otp_code=otp.otp_code,
                )
                logger.info(f"OTP email task queued for {dto.email} (OTP ID: {otp.id})")
            except (OperationalError, ConnectionError) as celery_error:
                # If Celery/Redis is unavailable, log error but don't fail the request
                # The OTP is still created and can be verified
                logger.error(
                    f"Failed to queue OTP email task for {dto.email} (OTP ID: {otp.id}): {str(celery_error)}. "
                    f"OTP created but email sending may be delayed. Please ensure Celery worker is running.",
                    exc_info=True,
                    extra={"otp_id": str(otp.id), "email": dto.email},
                )
        elif dto.otp_type == "sms" and dto.phone_number:
            from kombu.exceptions import OperationalError

            from tasks.otp_tasks import send_otp_sms_task

            try:
                # Send SMS in background
                send_otp_sms_task.delay(
                    phone_number=dto.phone_number,
                    otp_code=otp.otp_code,
                )
                logger.info(f"OTP SMS task queued for {dto.phone_number} (OTP ID: {otp.id})")
            except (OperationalError, ConnectionError) as celery_error:
                # If Celery/Redis is unavailable, log error but don't fail the request
                # The OTP is still created and can be verified
                logger.error(
                    f"Failed to queue OTP SMS task for {dto.phone_number} (OTP ID: {otp.id}): {str(celery_error)}. "
                    f"OTP created but SMS sending may be delayed. Please ensure Celery worker is running.",
                    exc_info=True,
                    extra={"otp_id": str(otp.id), "phone_number": dto.phone_number},
                )

        return {
            "message": f"OTP sent successfully to your {dto.otp_type}",
            "expires_in_minutes": OTPService.OTP_EXPIRY_MINUTES,
        }


class VerifyOTPUseCase:
    """Use case for verifying an OTP and returning tokens."""

    def __init__(
        self,
        otp_repository: OTPRepository,
        user_repository: UserRepository,
        user_domain_service: UserDomainService,
        session_repository: SessionRepository,
        device_repository: DeviceRepository,
    ):
        """Initialize use case."""
        self.otp_repository = otp_repository
        self.user_repository = user_repository
        self.user_domain_service = user_domain_service
        self.session_repository = session_repository
        self.device_repository = device_repository

    def execute(
        self,
        dto: OTPVerifyDTO,
        generate_tokens_func: Callable,
        device_id: str | None = None,
        device_name: str | None = None,
        device_type: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponseDTO:
        """
        Execute OTP verification and return tokens.

        Args:
            dto: OTP verify DTO
            generate_tokens_func: Function to generate JWT tokens
            device_id: Optional device ID
            device_name: Optional device name
            device_type: Optional device type
            ip_address: Optional IP address
            user_agent: Optional user agent

        Returns:
            LoginResponseDTO with tokens and user info

        Raises:
            BaseAPIException: If OTP is invalid or expired
        """
        # Log OTP verification attempt
        identifier = dto.email or dto.phone_number or "Unknown"
        logger.info(
            f"OTP verification attempt - identifier: {identifier}, "
            f"code: {'*' * (len(dto.otp) - 2) + dto.otp[-2:] if len(dto.otp) > 2 else '**'}"
        )

        # Verify OTP
        is_valid, otp = OTPService.verify_otp(
            otp_repository=self.otp_repository,
            code=dto.otp,
            email=dto.email,
            phone_number=dto.phone_number,
        )

        if not otp:
            logger.warning(f"OTP not found - identifier: {identifier}")
            raise BaseAPIException(
                detail="OTP not found. Please request a new OTP code.",
                code="OTP_NOT_FOUND",
                status_code=400,
            )

        if not is_valid:
            # Check specific reasons for invalidity
            from django.utils import timezone

            logger.warning(
                f"OTP verification failed - OTP ID: {otp.id}, "
                f"identifier: {identifier}, "
                f"verified: {otp.verified}, "
                f"expired: {otp.expires_at <= timezone.now()}, "
                f"attempts: {otp.attempts}/{otp.max_attempts}"
            )

            if otp.verified:
                logger.warning(
                    f"OTP already used - OTP ID: {otp.id}, identifier: {identifier}, "
                    f"verified_at: {otp.verified_at}"
                )
                raise BaseAPIException(
                    detail="This OTP has already been used. Please request a new OTP code.",
                    code="OTP_ALREADY_USED",
                    status_code=400,
                )

            if otp.expires_at <= timezone.now():
                logger.warning(
                    f"OTP expired - OTP ID: {otp.id}, identifier: {identifier}, "
                    f"expires_at: {otp.expires_at}, current_time: {timezone.now()}"
                )
                raise BaseAPIException(
                    detail="OTP has expired. Please request a new OTP code.",
                    code="OTP_EXPIRED",
                    status_code=400,
                )

            if otp.attempts >= otp.max_attempts:
                logger.warning(
                    f"OTP max attempts exceeded - OTP ID: {otp.id}, identifier: {identifier}, "
                    f"attempts: {otp.attempts}/{otp.max_attempts}"
                )
                raise BaseAPIException(
                    detail=f"Maximum OTP verification attempts ({otp.max_attempts}) exceeded. Please request a new OTP code.",
                    code="OTP_MAX_ATTEMPTS_EXCEEDED",
                    status_code=400,
                )

            # If we get here, the code is incorrect
            remaining_attempts = otp.max_attempts - otp.attempts
            logger.warning(
                f"Invalid OTP code - OTP ID: {otp.id}, identifier: {identifier}, "
                f"attempts: {otp.attempts}/{otp.max_attempts}, "
                f"remaining: {remaining_attempts}"
            )
            raise BaseAPIException(
                detail=f"Invalid OTP code. You have {remaining_attempts} attempt(s) remaining.",
                code="INVALID_OTP_CODE",
                status_code=400,
            )

        # Log successful verification
        logger.info(
            f"OTP verified successfully - OTP ID: {otp.id}, identifier: {identifier}, "
            f"user_id: {otp.user_id}"
        )

        # Get user if exists
        user = None
        if otp.user_id:
            user = self.user_repository.get_by_id(otp.user_id)
            logger.debug(f"User found by OTP user_id: {otp.user_id}")
        elif otp.email:
            user = self.user_repository.get_by_email(otp.email)
            logger.debug(f"User found by OTP email: {otp.email}")
        # TODO: Add get_by_phone_number to UserRepository if needed for phone-based lookup

        if not user:
            logger.error(
                f"User not found after OTP verification - OTP ID: {otp.id}, "
                f"user_id: {otp.user_id}, email: {otp.email}, phone: {otp.phone_number}"
            )
            raise BaseAPIException(
                detail="User not found",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        # Verify email/phone if not already verified
        # If user verifies OTP, it means they have access to their email
        if not user.email_verified:
            logger.info(
                f"Verifying email/phone after OTP verification - user_id: {user.id}, "
                f"identifier: {identifier}, account_created_at: {user.created_at}"
            )
            user.email_verified = True
            user = self.user_repository.update(user)

        # Start session
        session = self.user_domain_service.start_session(
            user_id=user.id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Register or update device
        if device_id:
            from uuid import uuid4

            from django.utils import timezone

            from domain.users.entities import Device

            device = self.device_repository.get_by_device_id(device_id)
            if device:
                # Update existing device
                device.last_used_at = timezone.now()
                if device_name:
                    device.device_name = device_name
                if device_type:
                    device.device_type = device_type
                if ip_address:
                    device.ip_address = ip_address
                if user_agent:
                    device.user_agent = user_agent
                device.updated_at = timezone.now()
                self.device_repository.update(device)
            else:
                # Create new device
                device = Device(
                    id=uuid4(),
                    user_id=user.id,
                    device_id=device_id,
                    device_name=device_name,
                    device_type=device_type,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    last_used_at=timezone.now(),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                self.device_repository.create(device)

        # Generate tokens
        tokens = generate_tokens_func(user)

        # Create refresh token
        self.user_domain_service.create_refresh_token(
            user_id=user.id,
            token=tokens["refresh"],
            device_id=device_id,
            ip_address=ip_address,
        )

        # Update last login
        from django.utils import timezone

        user.last_login = timezone.now()
        user = self.user_repository.update(user)

        logger.info(
            f"OTP verification completed successfully - user_id: {user.id}, "
            f"identifier: {identifier}, session_id: {session.id}, device_id: {device_id}"
        )

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
                email_verified=user.email_verified,
                is_staff=user.is_staff,
                is_superuser=user.is_superuser,
                last_login=user.last_login,
                address=user.address,
                avatar_url=user.avatar_url,
                created_at=user.created_at,
                updated_at=user.updated_at,
            ),
            expires_in=3600,  # 1 hour
        )
