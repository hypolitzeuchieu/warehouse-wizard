from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email(self, subject, message, recipient_list, html_message=None):
    """
    Generic function to send emails asynchronously.

    :param subject: Email subject.
    :param message: Email plain text content.
    :param recipient_list: List of recipient email addresses.
    :param html_message: HTML version of the email (optional).
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=recipient_list,
            fail_silently=False,
            html_message=html_message
        )
        logger.info(f"Email sent successfully to {recipient_list}")
    except Exception as exc:
        logger.error(f"Error sending email to {recipient_list}: {exc}")
        self.retry(exc=exc)
