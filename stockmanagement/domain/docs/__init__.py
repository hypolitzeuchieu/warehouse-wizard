"""Documentation domain module."""

from domain.docs.entities import DocumentationCredential
from domain.docs.repositories import DocumentationCredentialRepository

__all__ = [
    "DocumentationCredential",
    "DocumentationCredentialRepository",
]
