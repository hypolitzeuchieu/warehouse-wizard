"""Documentation credential repository implementations."""

from __future__ import annotations

from uuid import UUID

from django.utils import timezone

from domain.docs.entities import DocumentationCredential
from domain.docs.repositories import DocumentationCredentialRepository
from infrastructure.persistence.models.doc_credential_models import (
    DocumentationCredential as DocumentationCredentialModel,
)


class DocumentationCredentialRepositoryImpl(DocumentationCredentialRepository):
    """Django implementation of DocumentationCredentialRepository."""

    def get_by_id(self, credential_id: UUID) -> DocumentationCredential | None:
        """Get credential by ID."""
        try:
            credential_model = DocumentationCredentialModel.objects.get(id=credential_id)
            return self._to_entity(credential_model)
        except DocumentationCredentialModel.DoesNotExist:
            return None

    def get_by_username(self, username: str) -> DocumentationCredential | None:
        """Get credential by username."""
        try:
            credential_model = DocumentationCredentialModel.objects.get(username=username)
            return self._to_entity(credential_model)
        except DocumentationCredentialModel.DoesNotExist:
            return None

    def get_active(self) -> DocumentationCredential | None:
        """Get the active credential (if any)."""
        try:
            credential_model = DocumentationCredentialModel.objects.filter(
                is_active=True, expires_at__gt=timezone.now()
            ).first()
            if credential_model:
                return self._to_entity(credential_model)
            return None
        except DocumentationCredentialModel.DoesNotExist:
            return None

    def get_all(self) -> list[DocumentationCredential]:
        """Get all credentials."""
        credentials = DocumentationCredentialModel.objects.all()
        return [self._to_entity(cred) for cred in credentials]

    def create(self, credential: DocumentationCredential, password: str) -> DocumentationCredential:
        """Create a new credential."""
        credential_model = DocumentationCredentialModel(
            id=credential.id,
            username=credential.username,
            expires_at=credential.expires_at,
            is_active=credential.is_active,
        )
        credential_model.set_password(password)
        credential_model.save()
        return self._to_entity(credential_model)

    def update(self, credential: DocumentationCredential) -> DocumentationCredential:
        """Update an existing credential."""
        credential_model = DocumentationCredentialModel.objects.get(id=credential.id)
        credential_model.username = credential.username
        credential_model.expires_at = credential.expires_at
        credential_model.is_active = credential.is_active
        credential_model.save()
        return self._to_entity(credential_model)

    def delete(self, credential_id: UUID) -> None:
        """Delete a credential."""
        DocumentationCredentialModel.objects.filter(id=credential_id).delete()

    def delete_expired(self) -> int:
        """Delete expired credentials."""
        count, _ = DocumentationCredentialModel.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        return count

    def deactivate_all(self) -> int:
        """Deactivate all active credentials."""
        count = DocumentationCredentialModel.objects.filter(is_active=True).update(is_active=False)
        return count

    def verify_password(self, credential_id: UUID, password: str) -> bool:
        """Verify password for a credential."""
        try:
            credential_model = DocumentationCredentialModel.objects.get(id=credential_id)
            return credential_model.check_password(password)
        except DocumentationCredentialModel.DoesNotExist:
            return False

    def _to_entity(self, credential_model: DocumentationCredentialModel) -> DocumentationCredential:
        """Convert Django model to domain entity."""
        return DocumentationCredential(
            id=credential_model.id,
            username=credential_model.username,
            password_hash=credential_model.password_hash,
            expires_at=credential_model.expires_at,
            is_active=credential_model.is_active,
            created_at=credential_model.created_at,
            updated_at=credential_model.updated_at,
        )
