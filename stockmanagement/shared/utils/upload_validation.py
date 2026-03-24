"""Upload validation utilities for serializers."""

from __future__ import annotations

from django.conf import settings
from rest_framework import serializers


def validate_max_upload_size(file_obj, field_name: str = "file") -> None:
    """
    Validate uploaded file size for DRF serializers.

    Args:
        file_obj: Uploaded file (InMemoryUploadedFile / TemporaryUploadedFile)
        field_name: Used for clearer error messages

    Raises:
        serializers.ValidationError: If file is too large
    """
    if not file_obj:
        return

    max_bytes = int(getattr(settings, "MAX_MEDIA_UPLOAD_SIZE_BYTES", 1 * 1024 * 1024))
    size = getattr(file_obj, "size", None)
    if size is None:
        return

    if size > max_bytes:
        size_mb = size / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        raise serializers.ValidationError(
            f"{field_name} is too large ({size_mb:.1f}MB). Max allowed is {max_mb}MB.",
        ) from None
