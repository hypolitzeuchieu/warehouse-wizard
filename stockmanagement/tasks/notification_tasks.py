"""Celery tasks for sending notifications."""

from __future__ import annotations

import logging
from uuid import UUID

from celery import shared_task

from domain.notifications.repositories import NotificationRepository
from domain.users.repositories import UserRepository
from infrastructure.messaging.email_service import EmailService
from infrastructure.messaging.sms_service import SMSService
from infrastructure.persistence.repositories import (
    NotificationRepositoryImpl,
    UserRepositoryImpl,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_task(self, notification_id: UUID) -> dict:
    """
    Send notification via email (priority) or SMS (fallback).

    Priority order:
    1. Email (if user has email)
    2. SMS (if user has phone_number but no email)

    Args:
        notification_id: ID of the notification to send

    Returns:
        Dictionary with sending status:
        {
            "sent": bool,
            "method": "email" | "sms" | "none",
            "user_id": UUID,
            "notification_id": UUID
        }
    """
    try:
        notification_repository: NotificationRepository = NotificationRepositoryImpl()
        user_repository: UserRepository = UserRepositoryImpl()
        email_service = EmailService()
        sms_service = SMSService()

        notification = notification_repository.get_by_id(notification_id)
        if not notification or not notification.user_id:
            logger.warning(f"Notification {notification_id} not found or has no user")
            return {
                "sent": False,
                "method": "none",
                "reason": "notification_not_found_or_no_user",
                "notification_id": str(notification_id),
            }

        user = user_repository.get_by_id(notification.user_id)
        if not user:
            logger.warning(f"User {notification.user_id} not found")
            return {
                "sent": False,
                "method": "none",
                "reason": "user_not_found",
                "user_id": str(notification.user_id),
                "notification_id": str(notification_id),
            }

        if user.email:
            try:
                success = email_service.send_notification_email(
                    email=user.email,
                    subject=notification.title,
                    message=notification.message,
                )

                if success:
                    logger.info(
                        f"Notification sent via EMAIL to {user.email} "
                        f"(notification {notification_id}, user {user.id})"
                    )
                    return {
                        "sent": True,
                        "method": "email",
                        "user_id": str(user.id),
                        "notification_id": str(notification_id),
                        "recipient": user.email,
                    }
                else:
                    logger.warning(
                        f"Failed to send notification email to {user.email}, "
                        f"will try SMS if phone_number available"
                    )
            except Exception as e:
                logger.error(
                    f"Error sending notification email to {user.email}: {str(e)}",
                    exc_info=True,
                )

        if user.phone_number:
            try:
                sms_message = f"{notification.title}: {notification.message}"
                success = sms_service.send_notification_sms(
                    phone_number=user.phone_number,
                    message=sms_message,
                )

                if success:
                    logger.info(
                        f"Notification sent via SMS to {user.phone_number} "
                        f"(notification {notification_id}, user {user.id})"
                    )
                    return {
                        "sent": True,
                        "method": "sms",
                        "user_id": str(user.id),
                        "notification_id": str(notification_id),
                        "recipient": user.phone_number,
                    }
                else:
                    logger.warning(f"Failed to send notification SMS to {user.phone_number}")
            except Exception as e:
                logger.error(
                    f"Error sending notification SMS to {user.phone_number}: {str(e)}",
                    exc_info=True,
                )

        logger.warning(
            f"Could not send notification {notification_id} to user {user.id}: "
            f"email={'available' if user.email else 'not_available'}, "
            f"phone={'available' if user.phone_number else 'not_available'}"
        )
        return {
            "sent": False,
            "method": "none",
            "reason": "no_contact_method_available_or_all_failed",
            "user_id": str(user.id),
            "notification_id": str(notification_id),
            "has_email": bool(user.email),
            "has_phone": bool(user.phone_number),
        }

    except Exception as exc:
        logger.error(
            f"Error in send_notification_task for notification {notification_id}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc) from exc
