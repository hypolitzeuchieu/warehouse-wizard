"""OTP generation and validation service."""

from __future__ import annotations

import random
import string
from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4

from django.utils import timezone

from domain.users.entities import OTP
from domain.users.repositories import OTPRepository


class OTPService:
    """Service for OTP generation and validation."""

    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    MAX_ATTEMPTS = 3

    @staticmethod
    def generate_otp_code(length: int = OTP_LENGTH) -> str:
        """
        Generate a random OTP code.

        Args:
            length: Length of OTP code (default: 6)

        Returns:
            Random OTP code string
        """
        return "".join(random.choices(string.digits, k=length))

    @staticmethod
    def create_otp(
        otp_repository: OTPRepository,
        user_id: Optional[UUID] = None,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        purpose: str = "verification",
        otp_type: str = "email",
    ) -> OTP:
        """
        Create and store a new OTP.

        Args:
            otp_repository: OTP repository
            user_id: User ID (optional)
            email: Email address (optional)
            phone_number: Phone number (optional)
            purpose: Purpose of OTP (signup, login, etc.)
            otp_type: Type of OTP (email or sms)

        Returns:
            Created OTP entity
        """
        # Invalidate ALL previous pending OTPs for the same identifier and purpose
        # This ensures only one valid OTP exists at a time (business rule)
        invalidated_count = otp_repository.invalidate_all_pending(
            email=email,
            phone_number=phone_number,
            purpose=purpose,
            otp_type=otp_type,
        )
        
        if invalidated_count > 0:
            logger.info(
                f"Invalidated {invalidated_count} pending OTP(s) for "
                f"identifier: {email or phone_number}, purpose: {purpose}, type: {otp_type}"
            )
        # Generate new OTP
        otp_code = OTPService.generate_otp_code()
        expires_at = timezone.now() + timedelta(minutes=OTPService.OTP_EXPIRY_MINUTES)

        otp = OTP(
            id=uuid4(),
            user_id=user_id,
            email=email,
            phone_number=phone_number,
            otp_code=otp_code,
            otp_type=otp_type,
            purpose=purpose,
            expires_at=expires_at,
            verified=False,
            verified_at=None,
            attempts=0,
            max_attempts=OTPService.MAX_ATTEMPTS,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        return otp_repository.create(otp)

    @staticmethod
    def verify_otp(
        otp_repository: OTPRepository,
        code: str,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> tuple[bool, Optional[OTP]]:
        """
        Verify an OTP code.

        Args:
            otp_repository: OTP repository
            code: OTP code to verify
            email: Email address (optional)
            phone_number: Phone number (optional)

        Returns:
            Tuple of (is_valid, otp_entity)
        """
        otp = otp_repository.get_by_code(code, email=email, phone_number=phone_number)

        if not otp:
            return False, None

        if not otp.is_valid():
            return False, otp

        # Verify the code
        is_valid = otp.verify(code)
        if is_valid:
            otp_repository.update(otp)

        return is_valid, otp

