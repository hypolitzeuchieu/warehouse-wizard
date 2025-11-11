"""Base ViewSet with APIResponseMixin integration."""

from __future__ import annotations

from rest_framework.viewsets import ViewSet

from shared.views.api_response_mixin import APIResponseMixin


class BaseViewSet(APIResponseMixin, ViewSet):
    """Base ViewSet that integrates APIResponseMixin for standardized responses."""
    pass

