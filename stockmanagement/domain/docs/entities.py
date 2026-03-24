"""Documentation domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.utils import timezone


@dataclass
class DocumentationCredential:
    """Documentation credential entity for securing API documentation access."""

    id: UUID
    username: str
    password_hash: str
    expires_at: datetime
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def is_valid(self) -> bool:
        """Check if credential is valid (active and not expired).

        Returns:
            True if credential is active and not expired, False otherwise
        """
        return self.is_active and self.expires_at > timezone.now()
