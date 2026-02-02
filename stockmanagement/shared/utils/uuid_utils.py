"""UUID utilities for consistent comparison (e.g. JWT may send UUID as str)."""

from __future__ import annotations

from uuid import UUID


def normalize_uuid(value: UUID | str | None) -> UUID | None:
    """Normalize value to UUID type (handles str from JSON/JWT)."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def compare_uuids(uuid1: UUID | str | None, uuid2: UUID | str | None) -> bool:
    """Compare two UUIDs safely, handling UUID and string types."""
    n1 = normalize_uuid(uuid1)
    n2 = normalize_uuid(uuid2)
    if n1 is None or n2 is None:
        return False
    return n1 == n2
