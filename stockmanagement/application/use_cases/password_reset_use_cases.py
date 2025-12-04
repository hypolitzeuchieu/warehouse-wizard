"""Password reset use cases."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from application.dto.user_dto import ForgotPasswordDTO, ResetPasswordDTO
from domain.users.entities import PasswordResetToken
from domain.users.repositories import PasswordResetTokenRepository, UserRepository
from shared.exceptions.base import BaseAPIException
from shared.services.otp_service import OTPService
from tasks.password_reset_tasks import send_password_reset_email_task, send_password_reset_sms_task

logger = logging.getLogger(__name__)


class ForgotPasswordUseCase:
    """Use case for forgot password."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_reset_token_repository: PasswordResetTokenRepository,
    ):
        """Initialize use case."""
        self.user_repository = user_repository
        self.password_reset_token_repository = password_reset_token_repository

    def execute(self, dto: ForgotPasswordDTO) -> dict:
        """
        Execute forgot password request.

        Args:
            dto: Forgot password DTO

        Returns:
            Dictionary with success message

        Raises:
            BaseAPIException: If sending fails (but not if user not found for security)
        """
        expiration_minutes = int(getattr(settings, "PASSWORD_RESET_EXPIRY_MINUTES", 10))

        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")

        generic_message = "If the email or phone number exists, a reset link/code has been sent."

        user = None
        if dto.email:
            user = self.user_repository.get_by_email(dto.email)
        elif dto.phone_number:
            user = self.user_repository.get_by_phone_number(dto.phone_number)

        if not user:
            return {
                "message": generic_message,
                "expires_in_minutes": expiration_minutes,
            }

        self.password_reset_token_repository.invalidate_user_tokens(
            user_id=user.id, reset_type=dto.reset_type
        )

        if dto.reset_type == "email":
            token = secrets.token_urlsafe(32)
            code = None
        else:
            code = OTPService.generate_otp_code()
            token = None

        expires_at = timezone.now() + timedelta(minutes=expiration_minutes)
        reset_token_entity = PasswordResetToken(
            id=uuid4(),
            user_id=user.id,
            email=dto.email,
            phone_number=dto.phone_number,
            token=token,
            code=code,
            reset_type=dto.reset_type,
            expires_at=expires_at,
            used=False,
            used_at=None,
            attempts=0,
            max_attempts=3,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        reset_token = self.password_reset_token_repository.create(reset_token_entity)

        if dto.reset_type == "email" and dto.email:
            reset_url = f"{frontend_url}/reset-password?token={token}"

            send_password_reset_email_task.delay(
                email=dto.email,
                reset_url=reset_url,
                token=token,
            )
            logger.info(
                f"Password reset email task queued for {dto.email} (user: {user.id}, token_id: {reset_token.id})"
            )
        elif dto.reset_type == "sms" and dto.phone_number:

            send_password_reset_sms_task.delay(
                phone_number=dto.phone_number,
                code=code,
            )
            logger.info(
                f"Password reset SMS task queued for {dto.phone_number} (user: {user.id}, token_id: {reset_token.id})"
            )

        return {
            "message": generic_message,
            "expires_in_minutes": expiration_minutes,
        }


class ResetPasswordUseCase:
    """Use case for reset password."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_reset_token_repository: PasswordResetTokenRepository,
    ):
        """Initialize use case."""
        self.user_repository = user_repository
        self.password_reset_token_repository = password_reset_token_repository

    def execute(self, dto: ResetPasswordDTO) -> dict:
        """
        Execute password reset.

        Args:
            dto: Reset password DTO

        Returns:
            Dictionary with success message

        Raises:
            BaseAPIException: If token/code is invalid or expired
        """

        reset_token = None

        if dto.token:
            reset_token = self.password_reset_token_repository.get_by_token(dto.token)
            if not reset_token:
                raise BaseAPIException(
                    detail="Invalid or expired reset token",
                    code="INVALID_RESET_TOKEN",
                    status_code=400,
                )
        elif dto.code:
            reset_token = self.password_reset_token_repository.get_latest_by_code(dto.code)

        if not reset_token:
            raise BaseAPIException(
                detail="Invalid or expired reset code/token",
                code="INVALID_RESET_CODE",
                status_code=400,
            )

        if not reset_token.is_valid():
            if reset_token.attempts >= reset_token.max_attempts:
                raise BaseAPIException(
                    detail="Maximum reset attempts exceeded",
                    code="MAX_ATTEMPTS_EXCEEDED",
                    status_code=400,
                )
            reset_token.attempts += 1
            reset_token.updated_at = timezone.now()
            self.password_reset_token_repository.update(reset_token)
            raise BaseAPIException(
                detail="Invalid or expired reset token/code",
                code="INVALID_RESET_TOKEN",
                status_code=400,
            )

        if len(dto.new_password) < 8:
            reset_token.attempts += 1
            reset_token.updated_at = timezone.now()
            self.password_reset_token_repository.update(reset_token)
            raise BaseAPIException(
                detail="Password must be at least 8 characters long",
                code="WEAK_PASSWORD",
                status_code=400,
            )

        user = self.user_repository.get_by_id(reset_token.user_id)
        if not user:
            raise BaseAPIException(
                detail="User not found",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        updated_user = self.user_repository.update_password(user.id, dto.new_password)
        user = updated_user

        reset_token.used = True
        reset_token.used_at = timezone.now()
        reset_token.updated_at = timezone.now()
        self.password_reset_token_repository.update(reset_token)

        self.password_reset_token_repository.invalidate_user_tokens(user_id=user.id)

        return {"message": "Password reset successfully"}
