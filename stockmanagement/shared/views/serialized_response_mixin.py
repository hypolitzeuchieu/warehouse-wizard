"""Mixin enforcing serializer-backed API responses."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rest_framework import status


class SerializedResponseMixin:
    """Provide helpers to serialize DTOs/dicts before returning responses."""

    def serialized_response(
        self,
        serializer_class: type,
        data: Any,
        *,
        message: str = "Success",
        status_code: int = status.HTTP_200_OK,
        many: bool = False,
        context: dict[str, Any] | None = None,
    ):
        """
        Serialize data using the provided serializer before returning success response.

        Args:
            serializer_class: DRF serializer class with optional `from_dto`/`from_dict`.
            data: DTO, dataclass, dict, or iterable of these objects.
            message: Response message.
            status_code: HTTP status code for the response.
            many: Whether data represents a collection.
            context: Optional serializer context.
        """
        serialized = (
            self._serialize_many(serializer_class, data, context=context or {})
            if many
            else self._serialize_single(serializer_class, data, context=context or {})
        )
        return self.success(
            message=message,
            data=serialized,
            status_code=status_code,
        )

    def _serialize_many(
        self,
        serializer_class: type,
        items: Iterable[Any],
        *,
        context: dict[str, Any],
    ) -> list[Any]:
        return [self._serialize_single(serializer_class, item, context=context) for item in items]

    def _serialize_single(
        self,
        serializer_class: type,
        item: Any,
        *,
        context: dict[str, Any],
    ) -> Any:
        if item is None:
            return None

        if hasattr(serializer_class, "from_dto"):
            return serializer_class.from_dto(item)
        if hasattr(serializer_class, "from_dict"):
            return serializer_class.from_dict(item)

        serializer = serializer_class(instance=item, context=context)
        return serializer.data
