"""Documentation credential use cases."""

from __future__ import annotations

import logging
import secrets
import string
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from domain.docs.entities import DocumentationCredential
from domain.docs.repositories import DocumentationCredentialRepository
from shared.exceptions.base import BaseAPIException

logger = logging.getLogger(__name__)


class GenerateDocCredentialUseCase:
    """Use case for generating documentation credentials."""

    def __init__(self, credential_repository: DocumentationCredentialRepository) -> None:
        """Initialize use case.

        Args:
            credential_repository: Repository for documentation credentials
        """
        self.credential_repository = credential_repository

    def execute(self, username: str, days_valid: int = 7) -> tuple[DocumentationCredential, str]:
        """Generate and create a new documentation credential.

        Args:
            username: Username for the credential (required)
            days_valid: Number of days the credential will be valid (default: 7)

        Returns:
            Tuple of (DocumentationCredential entity, plain text password)

        Raises:
            BaseAPIException: If username already exists or is invalid
        """
        if not username or not username.strip():
            raise BaseAPIException(
                detail="Username is required",
                code="USERNAME_REQUIRED",
                status_code=400,
            )

        username = username.strip()

        # Validate username length
        if len(username) < 3 or len(username) > 150:
            raise BaseAPIException(
                detail="Username must be between 3 and 150 characters",
                code="INVALID_USERNAME_LENGTH",
                status_code=400,
            )

        # Check if username already exists
        existing = self.credential_repository.get_by_username(username)
        if existing:
            raise BaseAPIException(
                detail=f"Username '{username}' already exists",
                code="USERNAME_ALREADY_EXISTS",
                status_code=400,
            )

        # Always generate a secure password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(16))

        # Deactivate all existing active credentials
        deactivated_count = self.credential_repository.deactivate_all()
        if deactivated_count > 0:
            logger.info(f"Deactivated {deactivated_count} existing documentation credentials")

        # Create new credential entity
        expires_at = timezone.now() + timedelta(days=days_valid)
        credential = DocumentationCredential(
            id=uuid4(),
            username=username,
            password_hash="",  # Will be set by repository
            expires_at=expires_at,
            is_active=True,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        # Create credential in repository (password will be hashed)
        created_credential = self.credential_repository.create(credential, password)

        logger.info(
            f"Generated new documentation credential: {username} (expires: {expires_at.isoformat()})"
        )

        return created_credential, password


class AuthenticateDocCredentialUseCase:
    """Use case for authenticating documentation credentials."""

    def __init__(self, credential_repository: DocumentationCredentialRepository) -> None:
        """Initialize use case.

        Args:
            credential_repository: Repository for documentation credentials
        """
        self.credential_repository = credential_repository

    def execute(self, username: str, password: str) -> DocumentationCredential:
        """Authenticate documentation credentials.

        Args:
            username: Username
            password: Plain text password

        Returns:
            DocumentationCredential entity if authentication succeeds

        Raises:
            BaseAPIException: If credentials are invalid or expired
        """
        # Get credential by username
        credential = self.credential_repository.get_by_username(username)
        if not credential:
            logger.warning(f"Documentation login attempt with non-existent username: {username}")
            raise BaseAPIException(
                detail="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        # Check if credential is valid (active and not expired)
        if not credential.is_valid():
            logger.warning(
                f"Documentation login attempt with expired/inactive credential: {username}"
            )
            raise BaseAPIException(
                detail="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        # Verify password
        password_valid = self.credential_repository.verify_password(credential.id, password)
        if not password_valid:
            logger.warning(f"Documentation login attempt with invalid password: {username}")
            raise BaseAPIException(
                detail="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        logger.info(f"Successful documentation login: {username}")
        return credential
