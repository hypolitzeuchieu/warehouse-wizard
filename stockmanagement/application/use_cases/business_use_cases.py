"""Business use cases."""

from typing import Optional
from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.business_dto import (
    BusinessCreateDTO,
    BusinessMemberCreateDTO,
    BusinessMemberResponseDTO,
    BusinessMemberUpdateDTO,
    BusinessResponseDTO,
    BusinessUpdateDTO,
)
from domain.business.entities import Business, BusinessMember
from domain.business.repositories import (
    BusinessMemberRepository,
    BusinessRepository,
)
from domain.business.services import BusinessDomainService
from domain.users.entities import UserRole
from domain.users.repositories import UserRepository
from shared.exceptions.base import BaseAPIException


class CreateBusinessUseCase:
    """Use case for creating a business."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        user_repository: UserRepository,
        owner_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.user_repository = user_repository
        self.owner_id = owner_id

    def execute(self, dto: BusinessCreateDTO) -> BusinessResponseDTO:
        """Execute business creation."""
        # Get user and verify they are active
        user = self.user_repository.get_by_id(self.owner_id)
        if not user:
            raise BaseAPIException(
                detail="User not found",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        if not user.is_active:
            raise BaseAPIException(
                detail="User account is not active. Please verify your OTP first.",
                code="ACCOUNT_INACTIVE",
                status_code=403,
            )

        # Check if unique_name already exists
        existing = self.business_repository.get_by_unique_name(
            dto.unique_name
        )
        if existing:
            raise BaseAPIException(
                detail="Business with this unique name already exists",
                code="UNIQUE_NAME_EXISTS",
                status_code=400,
            )

        # Create business entity
        business = Business(
            id=uuid4(),
            name=dto.name,
            unique_name=dto.unique_name,
            owner_id=self.owner_id,
            description=dto.description,
            address=dto.address,
            phone_number=dto.phone_number,
            email=dto.email,
            qr_code_url=None,  # Will be generated later
            logo_url=None,
            is_active=True,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            settings=dto.settings or {},
        )

        business = self.business_repository.create(business)

        # Change user role to OWNER if not already
        if user.role != UserRole.OWNER:
            user.role = UserRole.OWNER
            user.updated_at = timezone.now()
            self.user_repository.update(user)

        return self._to_dto(business)

    def _to_dto(self, business: Business) -> BusinessResponseDTO:
        """Convert business entity to DTO."""
        return BusinessResponseDTO(
            id=business.id,
            name=business.name,
            unique_name=business.unique_name,
            owner_id=business.owner_id,
            description=business.description,
            address=business.address,
            phone_number=business.phone_number,
            email=business.email,
            qr_code_url=business.qr_code_url,
            logo_url=business.logo_url,
            is_active=business.is_active,
            settings=business.settings,
            created_at=business.created_at,
            updated_at=business.updated_at,
        )


class UpdateBusinessUseCase:
    """Use case for updating a business."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: BusinessUpdateDTO) -> BusinessResponseDTO:
        """Execute business update."""
        # Check permissions
        business = self.business_repository.get_by_id(self.business_id)
        if not business:
            raise BaseAPIException(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
                status_code=404,
            )

        if not self.business_domain_service.can_user_manage_members(
            self.business_id, self.user_id
        ):
            raise BaseAPIException(
                detail="You don't have permission to update this business",
                code="PERMISSION_DENIED",
                status_code=403,
            )

        # Update business
        if dto.name is not None:
            business.name = dto.name
        if dto.description is not None:
            business.description = dto.description
        if dto.address is not None:
            business.address = dto.address
        if dto.phone_number is not None:
            business.phone_number = dto.phone_number
        if dto.email is not None:
            business.email = dto.email
        if dto.logo_url is not None:
            business.logo_url = dto.logo_url
        if dto.settings is not None:
            business.settings = dto.settings
        business.updated_at = timezone.now()

        business = self.business_repository.update(business)
        return self._to_dto(business)

    def _to_dto(self, business: Business) -> BusinessResponseDTO:
        """Convert business entity to DTO."""
        return BusinessResponseDTO(
            id=business.id,
            name=business.name,
            unique_name=business.unique_name,
            owner_id=business.owner_id,
            description=business.description,
            address=business.address,
            phone_number=business.phone_number,
            email=business.email,
            qr_code_url=business.qr_code_url,
            logo_url=business.logo_url,
            is_active=business.is_active,
            settings=business.settings,
            created_at=business.created_at,
            updated_at=business.updated_at,
        )


class DeleteBusinessUseCase:
    """Use case for deleting a business."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> None:
        """Execute business deletion."""
        # Check permissions (only owner can delete)
        if not self.business_domain_service.can_user_delete_business(
            self.business_id, self.user_id
        ):
            raise BaseAPIException(
                detail="Only the owner can delete the business",
                code="PERMISSION_DENIED",
                status_code=403,
            )

        self.business_repository.delete(self.business_id)


class AddBusinessMemberUseCase:
    """Use case for adding a business member."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_member_repository: BusinessMemberRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_member_repository = business_member_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: BusinessMemberCreateDTO) -> BusinessMemberResponseDTO:
        """Execute adding business member."""
        # Check permissions
        if not self.business_domain_service.can_user_manage_members(
            self.business_id, self.user_id
        ):
            raise BaseAPIException(
                detail="You don't have permission to add members",
                code="PERMISSION_DENIED",
                status_code=403,
            )

        # Check if user is already a member
        existing_members = (
            self.business_member_repository.get_business_members(
                self.business_id, active_only=True
            )
        )
        if any(member.user_id == dto.user_id for member in existing_members):
            raise BaseAPIException(
                detail="User is already a member of this business",
                code="USER_ALREADY_MEMBER",
                status_code=400,
            )

        # Validate role - only owner can add managers
        if dto.role == "manager":
            if not self.business_domain_service.can_user_manage_managers(
                self.business_id, self.user_id
            ):
                raise BaseAPIException(
                    detail="Only the owner can add managers",
                    code="PERMISSION_DENIED",
                    status_code=403,
                )

        # Create business member
        member = BusinessMember(
            id=uuid4(),
            business_id=self.business_id,
            user_id=dto.user_id,
            role=dto.role,
            is_active=True,
            joined_at=timezone.now(),
            left_at=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        member = self.business_member_repository.create(member)
        return self._to_dto(member)

    def _to_dto(
        self, member: BusinessMember
    ) -> BusinessMemberResponseDTO:
        """Convert business member entity to DTO."""
        return BusinessMemberResponseDTO(
            id=member.id,
            business_id=member.business_id,
            user_id=member.user_id,
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
            left_at=member.left_at,
            created_at=member.created_at,
            updated_at=member.updated_at,
        )


class RemoveBusinessMemberUseCase:
    """Use case for removing a business member."""

    def __init__(
        self,
        business_member_repository: BusinessMemberRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_member_repository = business_member_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, member_id: UUID) -> None:
        """Execute removing business member."""
        # Check permissions
        if not self.business_domain_service.can_user_manage_members(
            self.business_id, self.user_id
        ):
            raise BaseAPIException(
                detail="You don't have permission to remove members",
                code="PERMISSION_DENIED",
                status_code=403,
            )

        # Check if member is a manager - only owner can remove managers
        member = self.business_member_repository.get_by_id(member_id)
        if member and member.is_manager():
            if not self.business_domain_service.can_user_manage_managers(
                self.business_id, self.user_id
            ):
                raise BaseAPIException(
                    detail="Only the owner can remove managers",
                    code="PERMISSION_DENIED",
                    status_code=403,
                )

        self.business_member_repository.remove(member_id)

