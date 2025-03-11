from __future__ import annotations

import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from authentication.models import User
from channels.layers import get_channel_layer
from django.utils.timezone import now
from notifications.models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications to managers only.
    """

    @staticmethod
    def create_notification(product, notification_type, message):
        try:
            time_threshold = now() - timedelta(days=1)

            existing_notification = Notification.objects.filter(
                product=product,
                notification_type=notification_type,
                created_at__gte=time_threshold
            ).first()
            if existing_notification:
                logger.info(
                    f"Notification already sent for {notification_type} "
                    f"on {product.name}. Resending to managers.")
                NotificationService.send_notification_to_managers(existing_notification)
                return existing_notification

            notif = Notification.objects.create(
                product=product,
                notification_type=notification_type,
                message=message,
            )
            notif.refresh_from_db()

            NotificationService.send_notification_to_managers(notif)
            return notif
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return {'error': f"Unexpected error occurred: {str(e)}"}

    @staticmethod
    def send_notification_to_managers(notification):
        """
            Sends notification only to managers via WebSockets.
        """
        managers = User.objects.filter(role='manager')
        if not managers.exists():
            logger.warning('No managers found to notify.')
            return

        print(f"Sending notification to {managers.count()} managers")

        channel_layer = get_channel_layer()

        for manager in managers:
            async_to_sync(channel_layer.group_send)(
                f'notifications_{manager.id}',
                {
                    'type': 'send_notification',
                    'data': {
                        'notification_type': notification.notification_type,
                        'message': notification.message,
                        'product': notification.product.name,
                        'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    },
                },
            )
        print('Ws Notification sent to manager')

    @staticmethod
    def get_all_notifications():
        try:
            notifications = Notification.objects.all()
            return notifications
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {'error': f"Unexpected error: {str(e)}"}

    @staticmethod
    def get_notification(notif_id: str):
        try:
            notification = Notification.objects.filter(id=notif_id).first()
            return notification
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {'error': f"Unexpected error: {str(e)}"}
