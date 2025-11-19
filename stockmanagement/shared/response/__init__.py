"""Response mixins for standardized API responses."""

from shared.response.base_mixin import BaseResponseMixin
from shared.response.django_mixin import DjangoResponseMixin
from shared.response.drf_mixin import DRFResponseMixin

ResponseMixin = DjangoResponseMixin
APIResponseMixin = DRFResponseMixin

__all__ = [
    "BaseResponseMixin",
    "DjangoResponseMixin",
    "DRFResponseMixin",
    "ResponseMixin",
    "APIResponseMixin",
]
