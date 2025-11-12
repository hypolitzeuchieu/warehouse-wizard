"""SMS service implementation."""

from __future__ import annotations

import logging

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
            # TODO: Integrate with SMS provider (Twilio, AWS SNS, etc.)
            # For now, log the OTP (in production, this should send actual SMS)
            logger.info(f"OTP SMS would be sent to {phone_number}: {otp_code}")
            # In production, uncomment and configure:
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # client.messages.create(
            #     body=message,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=phone_number
            # )

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
            # Integrate with SMS provider (Twilio, AWS SNS, etc.)
            logger.info(f"Password reset SMS would be sent to {phone_number}: {code}")
            # In production, uncomment and configure:
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # client.messages.create(
            #     body=message,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=phone_number
            # )

            return True
        except Exception as e:
            logger.error(f"Failed to send password reset SMS to {phone_number}: {str(e)}")
            return False
