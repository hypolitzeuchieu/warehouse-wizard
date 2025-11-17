"""Notification service for REST API (WebSocket removed)."""

from __future__ import annotations

import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.utils.timezone import now

from infrastructure.persistence.models.notification_models import Notification
from infrastructure.persistence.models.user_models import RetailPulseUser

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications to managers only.
    """

    @staticmethod
    def create_notification(
        product=None, notification_type=None, message=None, user=None, business=None, title=None
    ):
        """
        Create a notification.

        Args:
            product: Optional product entity
            notification_type: Type of notification
            message: Notification message
            user: Optional user to notify
            business: Optional business
            title: Optional title (defaults to first 255 chars of message)

        Returns:
            Notification object or error dict
        """
        try:
            time_threshold = now() - timedelta(minutes=1)

            existing_notification = Notification.objects.filter(
                related_entity_id=product.id if product else None,
                user=user,
                notification_type=notification_type,
                created_at__gte=time_threshold,
            ).first()
            if existing_notification:
                logger.info(
                    f"Notification already sent for {notification_type} "
                    f"on {product.name if product else 'N/A'}. Resending to managers."
                )
                NotificationService.send_notification_to_managers(existing_notification)
                return existing_notification

            notif = Notification.objects.create(
                related_entity_id=product.id if product else None,
                related_entity_type="product" if product else None,
                notification_type=notification_type or "SYSTEM",
                title=title or (message[:255] if message else "Notification"),
                message=message or "",
                user=user,
                business=business,
                status="UNREAD",
            )
            notif.refresh_from_db()

            if user is None:
                NotificationService.send_notification_to_managers(notif)
            else:
                NotificationService.send_notification_to_user(notif, user)

            return notif
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return {"error": f"Unexpected error occurred: {str(e)}"}

    @staticmethod
    def send_notification_to_managers(notification):
        """
        Creates notification for managers (WebSocket removed - using REST API only).

        Notifications are now accessible via REST API endpoint /api/v1/notifications/.
        Clients should poll this endpoint or use external push service.
        """
        from domain.users.entities import UserRole

        managers = RetailPulseUser.objects.filter(role=UserRole.MANAGER.value)
        if not managers.exists():
            logger.warning("No managers found to notify.")
            return

        logger.info(
            f"Notification created for {managers.count()} managers. "
            f"Access via REST API /api/v1/notifications/"
        )

    @staticmethod
    def send_notification_to_user(notification, user):
        """
        Creates notification for a specific user (WebSocket removed - using REST API only).

        Args:
            notification: The notification object
            user: The user to notify

        Notifications are now accessible via REST API endpoint /api/v1/notifications/.
        Clients should poll this endpoint or use external push service.
        """
        logger.info(
            f"Notification created for user {user.id}. "
            f"Access via REST API /api/v1/notifications/"
        )

    @staticmethod
    def get_all_notifications():
        try:
            notifications = Notification.objects.all()
            return notifications
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def get_notification(notif_id: str):
        try:
            notification = Notification.objects.filter(id=notif_id).first()
            return notification
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def get_user_notifications(user_id, status=None, limit=None):
        """
        Get notifications for a specific user with optional status filtering.

        Args:
            user_id: The user ID to get notifications for
            status: Optional notification status to filter by
            limit: Optional limit on number of notifications to return

        Returns:
            QuerySet of notifications
        """
        try:
            # Get notifications for specific user or broadcast notifications (user=None)
            query = Q(user_id=user_id) | Q(user__isnull=True)

            if status:
                query &= Q(status=status)

            notifications = Notification.objects.filter(query).order_by("-created_at")

            if limit:
                notifications = notifications[:limit]

            return notifications
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def mark_as_read(notification_id):
        """
        Mark a notification as read.

        Args:
            notification_id: The UUID of the notification

        Returns:
            Updated notification or error dict
        """
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.mark_as_read()
            return notification
        except Notification.DoesNotExist:
            logger.error(f"Notification not found: {notification_id}")
            return {"error": f"Notification not found: {notification_id}"}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def mark_all_as_read(user_id):
        """
        Mark all unread notifications for a user as read.

        Args:
            user_id: The user ID to mark notifications for

        Returns:
            Count of notifications marked as read
        """
        try:
            query = (Q(user_id=user_id) | Q(user__isnull=True)) & Q(status="UNREAD")
            count = Notification.objects.filter(query).update(status="READ")
            logger.info(f"Marked {count} notifications as read for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def archive_notification(notification_id):
        """
        Archive a notification.

        Args:
            notification_id: The UUID of the notification

        Returns:
            Updated notification or error dict
        """
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.archive()
            return notification
        except Notification.DoesNotExist:
            logger.error(f"Notification not found: {notification_id}")
            return {"error": f"Notification not found: {notification_id}"}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def bulk_archive_old_notifications(months: int = 12):
        """
        Archive notifications older than X months.

        Args:
            months: Number of months to consider for archiving

        Returns:
            Count of archived notifications
        """
        try:
            cutoff_date = now() - relativedelta(months=months)

            count = Notification.objects.filter(
                created_at__lt=cutoff_date, status__in=["UNREAD", "READ"]
            ).update(status="ARCHIVED")

            logger.info(f"Archived {count} old notifications")
            return count
        except Exception as e:
            logger.error(f"Error archiving old notifications: {str(e)}")
            return {"error": f"Error archiving old notifications: {str(e)}"}
