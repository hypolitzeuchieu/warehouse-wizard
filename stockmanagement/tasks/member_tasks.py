"""Celery tasks for member management."""

from __future__ import annotations

import logging

from celery import shared_task

from infrastructure.messaging.email_service import EmailService
from infrastructure.messaging.sms_service import SMSService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_member_credentials_email_task(
    self,
    email: str,
    username: str,
    password: str,
    business_name: str,
    role: str,
) -> bool:
    """Send member credentials email asynchronously via Celery."""
    try:
        email_service = EmailService()
        success = email_service.send_member_credentials_email(
            email=email,
            username=username,
            password=password,
            business_name=business_name,
            role=role,
        )
        if success:
            logger.info(f"Member credentials email sent successfully to {email}")
        else:
            logger.warning(f"Failed to send member credentials email to {email}")
        return success
    except Exception as exc:
        logger.error(
            f"Error sending member credentials email to {email}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_member_credentials_sms_task(
    self,
    phone_number: str,
    username: str,
    password: str,
    business_name: str,
    role: str,
    email: str | None = None,
) -> bool:
    """Send member credentials SMS asynchronously via Celery."""
    try:
        sms_service = SMSService()
        success = sms_service.send_member_credentials_sms(
            phone_number=phone_number,
            username=username,
            password=password,
            business_name=business_name,
            role=role,
            email=email,
        )
        if success:
            logger.info(f"Member credentials SMS sent successfully to {phone_number}")
        else:
            logger.warning(f"Failed to send member credentials SMS to {phone_number}")
        return success
    except Exception as exc:
        logger.error(
            f"Error sending member credentials SMS to {phone_number}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc
