"""Base ViewSet with APIResponseMixin integration."""

from __future__ import annotations

from rest_framework.viewsets import ViewSet

from shared.filters.list_filter_mixin import ListFilterMixin
from shared.views.api_response_mixin import APIResponseMixin
from shared.views.serialized_response_mixin import SerializedResponseMixin


class BaseViewSet(SerializedResponseMixin, ListFilterMixin, APIResponseMixin, ViewSet):
    """Base ViewSet with standardized responses, filtering, and serialization."""

    pass
