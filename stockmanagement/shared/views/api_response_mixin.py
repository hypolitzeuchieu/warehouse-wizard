"""APIResponseMixin for standardized API responses in DRF views."""

from __future__ import annotations

from shared.response.drf_mixin import DRFResponseMixin


class APIResponseMixin(DRFResponseMixin):
    """Alias for DRFResponseMixin for backward compatibility."""

    pass
