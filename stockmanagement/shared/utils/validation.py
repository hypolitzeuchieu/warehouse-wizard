"""Validation utilities for use cases."""

from enum import Enum
from typing import Any
from uuid import UUID

from domain.business.services import BusinessDomainService
from shared.exceptions.specific import BadRequestError, ForbiddenError, NotFoundError


def validate_business_access(
    business_domain_service: BusinessDomainService,
    business_id: UUID,
    user_id: UUID,
    error_message: str | None = None,
) -> None:
    """
    Validate that user has access to business.

    Shared utility function to avoid code duplication across use cases.

    Args:
        business_domain_service: Business domain service
        business_id: ID of the business
        user_id: ID of the user
        error_message: Optional custom error message

    Raises:
        ForbiddenError: If user doesn't have access
    """
    if not business_domain_service.user_has_access(business_id, user_id):
        raise ForbiddenError(
            detail=error_message or "You don't have access to this business",
            code="PERMISSION_DENIED",
        )


def validate_enum(
    value: str,
    enum_class: type[Enum],
    error_detail: str,
    error_code: str,
) -> Enum:
    """
    Validate enum value.

    Shared utility function to avoid code duplication in enum validation.

    Args:
        value: String value to validate
        enum_class: Enum class to validate against
        error_detail: Error detail message
        error_code: Error code

    Returns:
        Validated enum instance

    Raises:
        BadRequestError: If value is invalid
    """
    try:
        return enum_class(value)
    except ValueError as err:
        raise BadRequestError(
            detail=error_detail,
            code=error_code,
        ) from err


def validate_entity_belongs_to_business(
    entity: Any,
    business_id: UUID,
    entity_name: str,
    error_code: str | None = None,
) -> None:
    """
    Validate that entity exists and belongs to business.

    Shared utility function to avoid code duplication across use cases.

    Args:
        entity: Entity to validate (can be None)
        business_id: Expected business ID
        entity_name: Name of entity for error message (e.g., "Product", "Customer")
        error_code: Optional custom error code (defaults to "{ENTITY_NAME}_NOT_FOUND")

    Raises:
        NotFoundError: If entity doesn't exist or doesn't belong to business
    """
    if not entity or getattr(entity, "business_id", None) != business_id:
        default_code = f"{entity_name.upper().replace(' ', '_')}_NOT_FOUND"
        raise NotFoundError(
            detail=f"{entity_name} not found",
            code=error_code or default_code,
        )
