from __future__ import annotations

from apps.notifications.models import Notification
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Notification)
def send_notification_ws(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notifications_{instance.product.user.id}",
            {
                'type': 'send_notification',
                'data': {
                    'notification_type': instance.notification_type,
                    'message': instance.message,
                    'product': instance.product.name if instance.product else 'N/A',
                    'created_at': instance.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                },
            }
        )
