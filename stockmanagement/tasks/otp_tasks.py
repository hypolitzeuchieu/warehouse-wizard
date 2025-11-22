"""Celery tasks for OTP sending."""

from __future__ import annotations

import logging

from celery import shared_task

from infrastructure.messaging.email_service import EmailService
from infrastructure.messaging.sms_service import SMSService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_email_task(self, email: str, otp_code: str) -> bool:
    """
    Send OTP email asynchronously via Celery.

    Args:
        email: Recipient email address
        otp_code: OTP code to send

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        email_service = EmailService()
        success = email_service.send_otp_email(
            email=email,
            otp_code=otp_code,
        )
        if success:
            logger.info(f"OTP email sent successfully to {email}")
        else:
            logger.warning(f"Failed to send OTP email to {email}")
        return success
    except Exception as exc:
        logger.error(
            f"Error sending OTP email to {email}: {exc}",
            exc_info=True,
        )
        # Retry the task
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_sms_task(self, phone_number: str, otp_code: str) -> bool:
    """
    Send OTP SMS asynchronously via Celery.

    Args:
        phone_number: Recipient phone number
        otp_code: OTP code to send

    Returns:
        True if SMS sent successfully, False otherwise
    """
    try:
        sms_service = SMSService()
        logger.info(f"Attempting to send OTP SMS to {phone_number}: {otp_code}")
        success = sms_service.send_otp_sms(
            phone_number=phone_number,
            otp_code=otp_code,
        )
        if success:
            logger.info(f"OTP SMS sent successfully to {phone_number}")
        else:
            logger.warning(f"Failed to send OTP SMS to {phone_number}")
        return success
    except Exception as exc:
        logger.error(
            f"Error sending OTP SMS to {phone_number}: {exc}",
            exc_info=True,
        )
        # Retry the task
        raise self.retry(exc=exc) from exc
