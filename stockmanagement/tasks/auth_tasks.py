"""Celery tasks for authentication and token management."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cleanup_expired_tokens(self) -> dict:
    """
    Clean up expired OutstandingToken and BlacklistedToken records.

    This task should run daily to prevent database bloat from expired tokens.

    Returns:
        Dictionary with cleanup statistics
    """
    try:
        now = timezone.now()
        cutoff_date = now - timedelta(days=30)

        expired_outstanding = OutstandingToken.objects.filter(expires_at__lt=cutoff_date)
        deleted_outstanding = expired_outstanding.delete()[0]
        expired_blacklisted = BlacklistedToken.objects.filter(token__expires_at__lt=cutoff_date)
        deleted_blacklisted = expired_blacklisted.delete()[0]

        result = {
            "outstanding_tokens_deleted": deleted_outstanding,
            "blacklisted_tokens_deleted": deleted_blacklisted,
            "cutoff_date": cutoff_date.isoformat(),
        }

        logger.info(
            f"Token cleanup completed: {deleted_outstanding} outstanding tokens, "
            f"{deleted_blacklisted} blacklisted tokens deleted"
        )

        return result

    except Exception as exc:
        logger.error(
            f"Error in cleanup_expired_tokens task: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc
