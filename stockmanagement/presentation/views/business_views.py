"""Business API views."""

from uuid import UUID

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.business_use_cases import (
    AddBusinessMemberUseCase,
    CreateBusinessUseCase,
    DeleteBusinessUseCase,
    RemoveBusinessMemberUseCase,
    UpdateBusinessUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    UserRepositoryImpl,
)
from presentation.serializers.business_serializers import (
    BusinessCreateSerializer,
    BusinessMemberCreateSerializer,
    BusinessUpdateSerializer,
)
from shared.response.mixin import ResponseMixin


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_business_view(request: Request) -> Response:
    """Create business endpoint."""
    serializer = BusinessCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ResponseMixin.error(
            message="Validation error",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    try:
        dto = serializer.to_dto()
        use_case = CreateBusinessUseCase(
            business_repository=BusinessRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
            owner_id=request.user.id,
        )
        business_dto = use_case.execute(dto)

        # Get updated user info to return new role
        user = UserRepositoryImpl().get_by_id(request.user.id)

        return ResponseMixin.success(
            message="Business created successfully. Your role has been updated to OWNER.",
            data={
                "id": str(business_dto.id),
                "name": business_dto.name,
                "unique_name": business_dto.unique_name,
                "owner_id": str(business_dto.owner_id),
                "description": business_dto.description,
                "address": business_dto.address,
                "phone_number": business_dto.phone_number,
                "email": business_dto.email,
                "qr_code_url": business_dto.qr_code_url,
                "logo_url": business_dto.logo_url,
                "is_active": business_dto.is_active,
                "settings": business_dto.settings,
                "created_at": business_dto.created_at.isoformat(),
                "updated_at": business_dto.updated_at.isoformat(),
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "username": user.username,
                    "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                },
            },
            status_code=status.HTTP_201_CREATED,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_business_view(request: Request, business_id: UUID) -> Response:
    """Update business endpoint."""
    serializer = BusinessUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return ResponseMixin.error(
            message="Validation error",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    try:
        dto = serializer.to_dto()
        business_domain_service = BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )
        use_case = UpdateBusinessUseCase(
            business_repository=BusinessRepositoryImpl(),
            business_domain_service=business_domain_service,
            business_id=business_id,
            user_id=request.user.id,
        )
        business_dto = use_case.execute(dto)

        return ResponseMixin.success(
            message="Business updated successfully",
            data={
                "id": str(business_dto.id),
                "name": business_dto.name,
                "unique_name": business_dto.unique_name,
                "description": business_dto.description,
                "address": business_dto.address,
                "phone_number": business_dto.phone_number,
                "email": business_dto.email,
                "logo_url": business_dto.logo_url,
                "settings": business_dto.settings,
                "updated_at": business_dto.updated_at.isoformat(),
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_business_view(request: Request, business_id: UUID) -> Response:
    """Delete business endpoint."""
    try:
        business_domain_service = BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )
        use_case = DeleteBusinessUseCase(
            business_repository=BusinessRepositoryImpl(),
            business_domain_service=business_domain_service,
            business_id=business_id,
            user_id=request.user.id,
        )
        use_case.execute()

        return ResponseMixin.success(
            message="Business deleted successfully",
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_business_member_view(request: Request, business_id: UUID) -> Response:
    """Add business member endpoint."""
    serializer = BusinessMemberCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ResponseMixin.error(
            message="Validation error",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    try:
        dto = serializer.to_dto()
        business_domain_service = BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )
        use_case = AddBusinessMemberUseCase(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
            business_domain_service=business_domain_service,
            business_id=business_id,
            user_id=request.user.id,
        )
        member_dto = use_case.execute(dto)

        return ResponseMixin.success(
            message="Business member added successfully",
            data={
                "id": str(member_dto.id),
                "business_id": str(member_dto.business_id),
                "user_id": str(member_dto.user_id),
                "role": member_dto.role,
                "is_active": member_dto.is_active,
                "joined_at": member_dto.joined_at.isoformat(),
            },
            status_code=status.HTTP_201_CREATED,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_business_member_view(
    request: Request, business_id: UUID, member_id: UUID
) -> Response:
    """Remove business member endpoint."""
    try:
        business_domain_service = BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )
        use_case = RemoveBusinessMemberUseCase(
            business_member_repository=BusinessMemberRepositoryImpl(),
            business_domain_service=business_domain_service,
            business_id=business_id,
            user_id=request.user.id,
        )
        use_case.execute(member_id)

        return ResponseMixin.success(
            message="Business member removed successfully",
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)

