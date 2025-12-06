"""Documentation credential domain Django models."""

from __future__ import annotations

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from infrastructure.persistence.models.base_model import BaseModel


class DocumentationCredential(BaseModel):
    """Documentation credential model for securing API documentation access."""

    username = models.CharField(max_length=150, unique=True, db_index=True)
    password_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "documentation_credentials"
        verbose_name = "Documentation Credential"
        verbose_name_plural = "Documentation Credentials"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["is_active", "expires_at"]),
        ]

    def __str__(self) -> str:
        """String representation."""
        status = "Active" if self.is_active else "Inactive"
        return f"Documentation credential: {self.username} ({status})"

    def set_password(self, raw_password: str) -> None:
        """Set password hash from raw password.

        Args:
            raw_password: Plain text password
        """
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Check if raw password matches the hash.

        Args:
            raw_password: Plain text password to check

        Returns:
            True if password matches, False otherwise
        """

        return check_password(raw_password, self.password_hash)

    def is_valid(self) -> bool:
        """Check if credential is valid (active and not expired).

        Returns:
            True if credential is active and not expired, False otherwise
        """
        return self.is_active and self.expires_at > timezone.now()
