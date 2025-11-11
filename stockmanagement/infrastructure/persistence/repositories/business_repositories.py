"""Business repository implementations."""

from typing import Optional
from uuid import UUID

from django.utils import timezone

from domain.business.entities import Business, BusinessMember
from domain.business.repositories import (
    BusinessMemberRepository,
    BusinessRepository,
)
from infrastructure.persistence.models.business_models import (
    Business as BusinessModel,
    BusinessMember as BusinessMemberModel,
)


class BusinessRepositoryImpl(BusinessRepository):
    """Django implementation of BusinessRepository."""

    def get_by_id(self, business_id: UUID) -> Optional[Business]:
        """Get business by ID."""
        try:
            business_model = BusinessModel.objects.select_related("owner").get(
                id=business_id
            )
            return self._to_entity(business_model)
        except BusinessModel.DoesNotExist:
            return None

    def get_by_unique_name(self, unique_name: str) -> Optional[Business]:
        """Get business by unique name."""
        try:
            business_model = BusinessModel.objects.select_related("owner").get(
                unique_name=unique_name
            )
            return self._to_entity(business_model)
        except BusinessModel.DoesNotExist:
            return None

    def get_by_owner(self, owner_id: UUID) -> list[Business]:
        """Get businesses owned by a user."""
        businesses = BusinessModel.objects.filter(owner_id=owner_id).select_related(
            "owner"
        )
        return [self._to_entity(business) for business in businesses]

    def create(self, business: Business) -> Business:
        """Create a new business."""
        business_model = BusinessModel(
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
            settings=business.settings or {},
        )
        business_model.save()
        return self._to_entity(business_model)

    def update(self, business: Business) -> Business:
        """Update an existing business."""
        business_model = BusinessModel.objects.get(id=business.id)
        business_model.name = business.name
        business_model.unique_name = business.unique_name
        business_model.description = business.description
        business_model.address = business.address
        business_model.phone_number = business.phone_number
        business_model.email = business.email
        business_model.qr_code_url = business.qr_code_url
        business_model.logo_url = business.logo_url
        business_model.is_active = business.is_active
        business_model.settings = business.settings or {}
        business_model.save()
        return self._to_entity(business_model)

    def delete(self, business_id: UUID) -> None:
        """Delete a business."""
        BusinessModel.objects.filter(id=business_id).delete()

    def user_has_access(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user has access to business."""
        # Check if user is owner
        if BusinessModel.objects.filter(id=business_id, owner_id=user_id).exists():
            return True
        # Check if user is a member
        return BusinessMemberModel.objects.filter(
            business_id=business_id, user_id=user_id, is_active=True
        ).exists()

    def _to_entity(self, business_model: BusinessModel) -> Business:
        """Convert Django model to domain entity."""
        return Business(
            id=business_model.id,
            name=business_model.name,
            unique_name=business_model.unique_name,
            owner_id=business_model.owner_id,
            description=business_model.description,
            address=business_model.address,
            phone_number=business_model.phone_number,
            email=business_model.email,
            qr_code_url=business_model.qr_code_url,
            logo_url=business_model.logo_url,
            is_active=business_model.is_active,
            created_at=business_model.created_at,
            updated_at=business_model.updated_at,
            settings=business_model.settings,
        )


class BusinessMemberRepositoryImpl(BusinessMemberRepository):
    """Django implementation of BusinessMemberRepository."""

    def get_by_id(self, member_id: UUID) -> Optional[BusinessMember]:
        """Get business member by ID."""
        try:
            member_model = BusinessMemberModel.objects.select_related(
                "business", "user"
            ).get(id=member_id)
            return self._to_entity(member_model)
        except BusinessMemberModel.DoesNotExist:
            return None

    def get_business_members(
        self, business_id: UUID, active_only: bool = True
    ) -> list[BusinessMember]:
        """Get all members of a business."""
        query = BusinessMemberModel.objects.filter(business_id=business_id)
        if active_only:
            query = query.filter(is_active=True, left_at__isnull=True)
        members = query.select_related("user")
        return [self._to_entity(member) for member in members]

    def get_user_businesses(self, user_id: UUID) -> list[BusinessMember]:
        """Get all businesses a user is a member of."""
        members = BusinessMemberModel.objects.filter(
            user_id=user_id, is_active=True, left_at__isnull=True
        ).select_related("business")
        return [self._to_entity(member) for member in members]

    def get_managers(self, business_id: UUID) -> list[BusinessMember]:
        """Get all managers of a business."""
        managers = BusinessMemberModel.objects.filter(
            business_id=business_id, role="manager", is_active=True
        ).select_related("user")
        return [self._to_entity(member) for member in managers]

    def create(self, member: BusinessMember) -> BusinessMember:
        """Add a member to a business."""
        member_model = BusinessMemberModel(
            id=member.id,
            business_id=member.business_id,
            user_id=member.user_id,
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
            left_at=member.left_at,
        )
        member_model.save()
        return self._to_entity(member_model)

    def update(self, member: BusinessMember) -> BusinessMember:
        """Update a business member."""
        member_model = BusinessMemberModel.objects.get(id=member.id)
        member_model.role = member.role
        member_model.is_active = member.is_active
        member_model.left_at = member.left_at
        member_model.save()
        return self._to_entity(member_model)

    def remove(self, member_id: UUID) -> None:
        """Remove a member from a business."""
        BusinessMemberModel.objects.filter(id=member_id).update(
            is_active=False, left_at=timezone.now()
        )

    def is_manager(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if user is a manager of the business."""
        return BusinessMemberModel.objects.filter(
            business_id=business_id,
            user_id=user_id,
            role="manager",
            is_active=True,
        ).exists()

    def _to_entity(self, member_model: BusinessMemberModel) -> BusinessMember:
        """Convert Django model to domain entity."""
        return BusinessMember(
            id=member_model.id,
            business_id=member_model.business_id,
            user_id=member_model.user_id,
            role=member_model.role,
            is_active=member_model.is_active,
            joined_at=member_model.joined_at,
            left_at=member_model.left_at,
            created_at=member_model.created_at,
            updated_at=member_model.updated_at,
        )

