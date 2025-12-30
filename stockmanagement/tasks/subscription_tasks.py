"""Celery tasks for subscription management."""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import connection

from domain.subscription.services import SubscriptionDomainService
from infrastructure.persistence.repositories import (
    BusinessRepositoryImpl,
    SubscriptionRepositoryImpl,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=270,
)
def check_expired_subscriptions_task(self) -> dict:
    """
    Check for expired subscriptions and deactivate businesses.

    This task should be run periodically (e.g., daily) to:
    1. Find expired subscriptions
    2. Update their status
    3. Deactivate businesses with expired subscriptions
    """
    task_id = str(self.request.id)

    try:
        connection.close()

        subscription_domain_service = SubscriptionDomainService(
            subscription_repository=SubscriptionRepositoryImpl(),
            business_repository=BusinessRepositoryImpl(),
        )

        # Check and update expired subscriptions
        expired_subscriptions = (
            subscription_domain_service.check_and_update_expired_subscriptions()
        )

        # Deactivate businesses with expired subscriptions
        deactivated_businesses = (
            subscription_domain_service.deactivate_businesses_with_expired_subscriptions()
        )

        connection.close()

        logger.info(
            f"Expired subscriptions check completed - "
            f"expired_count: {len(expired_subscriptions)}, "
            f"deactivated_businesses: {len(deactivated_businesses)}, "
            f"task_id: {task_id}"
        )

        return {
            "status": "completed",
            "expired_subscriptions_count": len(expired_subscriptions),
            "deactivated_businesses_count": len(deactivated_businesses),
            "expired_subscription_ids": [str(sub.id) for sub in expired_subscriptions],
            "deactivated_business_ids": [str(bid) for bid in deactivated_businesses],
            "task_id": task_id,
        }

    except Exception as exc:
        logger.error(
            f"Error checking expired subscriptions: {exc}, task_id: {task_id}",
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=270,
)
def send_subscription_reminder_task(
    self, subscription_id: str, days_until_expiry: int
) -> dict:
    """
    Send subscription expiration reminder.

    Args:
        subscription_id: Subscription ID
        days_until_expiry: Days until subscription expires
    """
    task_id = str(self.request.id)

    try:
        connection.close()

        subscription_repository = SubscriptionRepositoryImpl()
        subscription = subscription_repository.get_by_id(subscription_id)

        if not subscription:
            logger.warning(
                f"Subscription {subscription_id} not found for reminder, task_id: {task_id}"
            )
            return {
                "status": "skipped",
                "reason": "Subscription not found",
                "task_id": task_id,
            }

        # Implement email/SMS notification sending
        # For now, just log the reminder
        logger.info(
            f"Subscription reminder - subscription_id: {subscription_id}, "
            f"business_id: {subscription.business_id}, "
            f"days_until_expiry: {days_until_expiry}, "
            f"task_id: {task_id}"
        )

        connection.close()

        return {
            "status": "completed",
            "subscription_id": subscription_id,
            "days_until_expiry": days_until_expiry,
            "task_id": task_id,
        }

    except Exception as exc:
        logger.error(
            f"Error sending subscription reminder: {exc}, task_id: {task_id}",
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc
