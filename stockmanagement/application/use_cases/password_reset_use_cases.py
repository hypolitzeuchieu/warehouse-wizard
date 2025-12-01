"""Password reset use cases."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from application.dto.user_dto import ForgotPasswordDTO, ResetPasswordDTO
from domain.users.repositories import UserRepository
from infrastructure.persistence.models.password_reset_models import (
    PasswordResetToken as PasswordResetTokenModel,
)
from infrastructure.persistence.models.user_models import RetailPulseUser as UserModel
from shared.exceptions.base import BaseAPIException
from shared.services.otp_service import OTPService
from tasks.password_reset_tasks import send_password_reset_email_task, send_password_reset_sms_task

logger = logging.getLogger(__name__)


class ForgotPasswordUseCase:
    """Use case for forgot password."""

    def __init__(
        self,
        user_repository: UserRepository,
    ):
        """Initialize use case."""
        self.user_repository = user_repository

    def execute(self, dto: ForgotPasswordDTO) -> dict:
        """
        Execute forgot password request.

        Args:
            dto: Forgot password DTO

        Returns:
            Dictionary with success message

        Raises:
            BaseAPIException: If user not found or sending fails
        """
        expiration_minutes = int(getattr(settings, "PASSWORD_RESET_EXPIRY_MINUTES", 10))

        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")

        user = None
        if dto.email:
            user = self.user_repository.get_by_email(dto.email)
        elif dto.phone_number:
            try:
                user_model = UserModel.objects.get(phone_number=dto.phone_number)
                user = self.user_repository.get_by_id(user_model.id)
            except UserModel.DoesNotExist:
                user = None

        if not user:
            return {
                "message": f"If the {dto.reset_type} exists, a reset link/code has been sent.",
                "expires_in_minutes": expiration_minutes,
            }

        try:
            user_model = UserModel.objects.get(id=user.id)
        except UserModel.DoesNotExist:
            return {
                "message": f"If the {dto.reset_type} exists, a reset link/code has been sent.",
                "expires_in_minutes": expiration_minutes,
            }

        PasswordResetTokenModel.objects.filter(
            user_id=user.id, used=False, reset_type=dto.reset_type
        ).update(used=True, used_at=timezone.now())

        if dto.reset_type == "email":
            token = secrets.token_urlsafe(32)
            code = None
        else:
            code = OTPService.generate_otp_code()
            token = None

        expires_at = timezone.now() + timedelta(minutes=expiration_minutes)
        reset_token = PasswordResetTokenModel.objects.create(
            id=uuid4(),
            user=user_model,
            email=dto.email,
            phone_number=dto.phone_number,
            token=token,
            code=code,
            reset_type=dto.reset_type,
            expires_at=expires_at,
            used=False,
            attempts=0,
            max_attempts=3,
        )

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
            "message": f"Password reset {dto.reset_type} sent successfully",
            "expires_in_minutes": expiration_minutes,
        }


class ResetPasswordUseCase:
    """Use case for reset password."""

    def __init__(self, user_repository: UserRepository):
        """Initialize use case."""
        self.user_repository = user_repository

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
            try:
                reset_token = PasswordResetTokenModel.objects.get(
                    token=dto.token, used=False, reset_type="email"
                )
            except PasswordResetTokenModel.DoesNotExist:
                raise BaseAPIException(
                    detail="Invalid or expired reset token",
                    code="INVALID_RESET_TOKEN",
                    status_code=400,
                ) from None
        elif dto.code:
            reset_token = (
                PasswordResetTokenModel.objects.filter(code=dto.code, used=False, reset_type="sms")
                .order_by("-created_at")
                .first()
            )

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
            reset_token.save()
            raise BaseAPIException(
                detail="Invalid or expired reset token/code",
                code="INVALID_RESET_TOKEN",
                status_code=400,
            )

        if len(dto.new_password) < 8:
            reset_token.attempts += 1
            reset_token.save()
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

        user_model = UserModel.objects.get(id=user.id)
        user_model.set_password(dto.new_password)
        user_model.save()

        user.updated_at = timezone.now()
        self.user_repository.update(user)

        reset_token.used = True
        reset_token.used_at = timezone.now()
        reset_token.save()

        PasswordResetTokenModel.objects.filter(user=user_model, used=False).update(
            used=True, used_at=timezone.now()
        )

        return {"message": "Password reset successfully"}
