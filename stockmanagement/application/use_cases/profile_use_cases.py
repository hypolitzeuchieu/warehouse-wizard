"""Profile use cases."""

from __future__ import annotations

from uuid import UUID

from django.utils import timezone

from application.dto.user_dto import ProfileUpdateDTO, UserResponseDTO
from domain.users.entities import User, UserRole
from domain.users.repositories import UserRepository
from shared.exceptions.base import BaseAPIException


class GetProfileUseCase:
    """Use case for getting user profile."""

    def __init__(self, user_repository: UserRepository):
        """Initialize use case."""
        self.user_repository = user_repository

    def execute(self, user_id: UUID) -> UserResponseDTO:
        """
        Get user profile.

        Args:
            user_id: User ID

        Returns:
            UserResponseDTO with user profile

        Raises:
            BaseAPIException: If user not found
        """
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise BaseAPIException(
                detail="User not found",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        return self._to_dto(user)

    def _to_dto(self, user: User) -> UserResponseDTO:
        """Convert user entity to DTO."""
        return UserResponseDTO(
            id=user.id,
            email=user.email or "",
            name=user.name,
            phone_number=user.phone_number,
            role=user.role.value if isinstance(user.role, UserRole) else user.role,
            is_active=user.is_active,
            is_staff=user.is_staff,
            is_superuser=user.is_superuser,
            last_login=user.last_login,
            address=user.address,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class UpdateProfileUseCase:
    """Use case for updating user profile."""

    def __init__(self, user_repository: UserRepository):
        """Initialize use case."""
        self.user_repository = user_repository

    def execute(self, user_id: UUID, dto: ProfileUpdateDTO) -> UserResponseDTO:
        """
        Update user profile.

        Args:
            user_id: User ID
            dto: Profile update DTO

        Returns:
            UserResponseDTO with updated user profile

        Raises:
            BaseAPIException: If user not found or validation fails
        """
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise BaseAPIException(
                detail="User not found",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        # Update user fields (name is not unique, so no need to check)
        if dto.name is not None:
            user.name = dto.name
        if dto.phone_number is not None:
            user.phone_number = dto.phone_number
        if dto.address is not None:
            user.address = dto.address
        if dto.avatar_url is not None:
            user.avatar_url = dto.avatar_url

        user.updated_at = timezone.now()
        user = self.user_repository.update(user)

        return self._to_dto(user)

    def _to_dto(self, user: User) -> UserResponseDTO:
        """Convert user entity to DTO."""
        return UserResponseDTO(
            id=user.id,
            email=user.email or "",
            name=user.name,
            phone_number=user.phone_number,
            role=user.role.value if isinstance(user.role, UserRole) else user.role,
            is_active=user.is_active,
            is_staff=user.is_staff,
            is_superuser=user.is_superuser,
            last_login=user.last_login,
            address=user.address,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

