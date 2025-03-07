from __future__ import annotations

from notifications.models import Notification
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
            'is_read',
        ]


class NotifSerializer(serializers.Serializer):
    notif_id = serializers.UUIDField(required=True)
