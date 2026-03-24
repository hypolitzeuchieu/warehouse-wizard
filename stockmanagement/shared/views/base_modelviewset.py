"""Base ModelViewSet with APIResponseMixin integration."""

from __future__ import annotations

from rest_framework.viewsets import ModelViewSet

from shared.views.api_response_mixin import APIResponseMixin


class BaseModelViewSet(APIResponseMixin, ModelViewSet):
    """Base ModelViewSet that integrates APIResponseMixin for standardized responses."""
    pass

