from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from notifications.models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications.
    """

    @staticmethod
    def create_notification(user, product, notification_type, message):
        try:
            notif = Notification.objects.create(
                user=user,
                product=product,
                notification_type=notification_type,
                message=message,
            )
            # send via WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'notifications',
                {
                    'type': 'send_notification',
                    'data': {
                        'notification_type': notif.notification_type,
                        'message': notif.message,
                        'product': notif.product.name,
                        'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    },
                },
            )
            return notif
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return {'error': f"Unexpected error occurred: {str(e)}"}

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
