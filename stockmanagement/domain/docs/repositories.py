"""Documentation domain repositories (interfaces)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from domain.docs.entities import DocumentationCredential


class DocumentationCredentialRepository(ABC):
    """Documentation credential repository interface."""

    @abstractmethod
    def get_by_id(self, credential_id: UUID) -> DocumentationCredential | None:
        """Get credential by ID.

        Args:
            credential_id: Credential ID

        Returns:
            DocumentationCredential if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> DocumentationCredential | None:
        """Get credential by username.

        Args:
            username: Username

        Returns:
            DocumentationCredential if found, None otherwise
        """
        pass

    @abstractmethod
    def get_active(self) -> DocumentationCredential | None:
        """Get the active credential (if any).

        Returns:
            Active DocumentationCredential if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all(self) -> list[DocumentationCredential]:
        """Get all credentials.

        Returns:
            List of all DocumentationCredential
        """
        pass

    @abstractmethod
    def create(self, credential: DocumentationCredential, password: str) -> DocumentationCredential:
        """Create a new credential.

        Args:
            credential: Credential entity
            password: Plain text password to hash

        Returns:
            Created DocumentationCredential
        """
        pass

    @abstractmethod
    def update(self, credential: DocumentationCredential) -> DocumentationCredential:
        """Update an existing credential.

        Args:
            credential: Credential entity to update

        Returns:
            Updated DocumentationCredential
        """
        pass

    @abstractmethod
    def delete(self, credential_id: UUID) -> None:
        """Delete a credential.

        Args:
            credential_id: Credential ID to delete
        """
        pass

    @abstractmethod
    def delete_expired(self) -> int:
        """Delete expired credentials.

        Returns:
            Number of deleted credentials
        """
        pass

    @abstractmethod
    def deactivate_all(self) -> int:
        """Deactivate all active credentials.

        Returns:
            Number of deactivated credentials
        """
        pass

    @abstractmethod
    def verify_password(self, credential_id: UUID, password: str) -> bool:
        """Verify password for a credential.

        Args:
            credential_id: Credential ID
            password: Plain text password to verify

        Returns:
            True if password is correct, False otherwise
        """
        pass
