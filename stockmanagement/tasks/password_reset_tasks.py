"""Celery tasks for password reset."""

from __future__ import annotations

import logging

from celery import shared_task

from infrastructure.messaging.email_service import EmailService
from infrastructure.messaging.sms_service import SMSService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email_task(self, email: str, reset_url: str, token: str) -> bool:
    """
    Send password reset email asynchronously via Celery.

    Args:
        email: Recipient email address
        reset_url: Password reset URL
        token: Reset token

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        email_service = EmailService()
        success = email_service.send_password_reset_email(
            email=email,
            reset_url=reset_url,
            token=token,
        )
        if success:
            logger.info(f"Password reset email sent successfully to {email}")
        else:
            logger.warning(f"Failed to send password reset email to {email}")
        return success
    except Exception as exc:
        logger.error(
            f"Error sending password reset email to {email}: {exc}",
            exc_info=True,
        )
        # Retry the task
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_sms_task(self, phone_number: str, code: str) -> bool:
    """
    Send password reset SMS asynchronously via Celery.

    Args:
        phone_number: Recipient phone number
        code: Reset code

    Returns:
        True if SMS sent successfully, False otherwise
    """
    try:
        sms_service = SMSService()
        success = sms_service.send_password_reset_sms(
            phone_number=phone_number,
            code=code,
        )
        if success:
            logger.info(f"Password reset SMS sent successfully to {phone_number}")
        else:
            logger.warning(f"Failed to send password reset SMS to {phone_number}")
        return success
    except Exception as exc:
        logger.error(
            f"Error sending password reset SMS to {phone_number}: {exc}",
            exc_info=True,
        )
        # Retry the task
        raise self.retry(exc=exc)

