"""Notification serializers."""

from __future__ import annotations

from rest_framework import serializers


class NotificationResponseSerializer(serializers.Serializer):
    """Serializer for notification responses."""

    id = serializers.UUIDField()
    notification_type = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    related_entity_type = serializers.CharField(allow_null=True, required=False)
    related_entity_id = serializers.UUIDField(allow_null=True, required=False)
    status = serializers.CharField()
    read_at = serializers.DateTimeField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    metadata = serializers.JSONField(required=False, allow_null=True)

    @classmethod
    def from_dict(cls, data: dict) -> dict:
        """
        Serialize notification dictionaries.

        Notifications currently come from the notification service as dictionaries,
        so we expose a helper that validates and normalizes them.
        """
        serializer = cls(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.data
