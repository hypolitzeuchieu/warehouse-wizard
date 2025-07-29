from __future__ import annotations

from apps.notifications.models import Notification
from rest_framework import serializers


class NotificationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'product',
            'product_name',
            'notification_type',
            'message',
            'created_at',
            'status',
        ]


class NotifSerializer(serializers.Serializer):
    notif_id = serializers.UUIDField(required=True)


class UserNotificationSerializer(serializers.Serializer):
    page_size = serializers.IntegerField(required=False, min_value=1, default=10)
    status = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_STATUS, required=False
    )


class WeekSerializer(serializers.Serializer):
    months = serializers.IntegerField(required=True)
