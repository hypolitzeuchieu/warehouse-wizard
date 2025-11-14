"""SMS service implementation."""

from __future__ import annotations

import logging

from django.conf import settings
from twilio.rest import Client

logger = logging.getLogger(__name__)


class SMSService:
    """Service for sending SMS messages."""

    @staticmethod
    def send_otp_sms(phone_number: str, otp_code: str) -> bool:
        """
        Send OTP via SMS.

        Args:
            phone_number: Recipient phone number
            otp_code: OTP code to send

        Returns:
            True if SMS sent successfully, False otherwise
        """
        try:
            message = (
                f"Your RetailPulse verification code is: {otp_code}\n\n"
                f"This code will expire in 10 minutes.\n\n"
                f"If you didn't request this code, please ignore this message."
            )

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number,
            )

            logger.info(f"OTP SMS sent successfully to {phone_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to send OTP SMS to {phone_number}: {str(e)}")
            return False

    @staticmethod
    def send_password_reset_sms(phone_number: str, code: str) -> bool:
        """
        Send password reset code via SMS.

        Args:
            phone_number: Recipient phone number
            code: Reset code to send

        Returns:
            True if SMS sent successfully, False otherwise
        """
        try:
            logger.info(f"Password reset SMS would be sent to {phone_number}: {code}")
            message = (
                f"Your RetailPulse password reset code is: {code}\n\n"
                f"This code will expire in 10 minutes.\n\nI"
                f"f you didn't request this code, please ignore this message."
            )

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message, from_=settings.TWILIO_PHONE_NUMBER, to=phone_number
            )

            return True
        except Exception as e:
            logger.error(f"Failed to send password reset SMS to {phone_number}: {str(e)}")
            return False

    @staticmethod
    def send_welcome_sms(phone_number: str, username: str) -> bool:
        """
        Send welcome message via SMS.

        Args:
            phone_number: Recipient phone number
            username: Name of the user

        Returns:
            True if SMS sent successfully, False otherwise
        """
        try:
            logger.info(f"Welcome SMS would be sent to {phone_number} for user {username}")
            message = (
                f"Hello {username},\n\nWelcome to RetailPulse! "
                f"Your account has been successfully created."
                f"\n\nBest regards,\nThe RetailPulse Team"
            )

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message, from_=settings.TWILIO_PHONE_NUMBER, to=phone_number
            )

            return True
        except Exception as e:
            logger.error(f"Failed to send welcome SMS to {phone_number}: {str(e)}")
            return False
