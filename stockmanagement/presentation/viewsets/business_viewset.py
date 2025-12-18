"""Business ViewSet using DDD architecture with use cases."""

from __future__ import annotations

from uuid import UUID

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.business_list_filter_dto import BusinessListFilterDTO
from application.dto.business_member_list_filter_dto import BusinessMemberListFilterDTO
from application.use_cases.business_use_cases import (
    AddBusinessMemberUseCase,
    CreateBusinessUseCase,
    DeleteBusinessUseCase,
    GetBusinessUseCase,
    ListBusinessesUseCase,
    ListBusinessMembersUseCase,
    RemoveBusinessMemberUseCase,
    UpdateBusinessUseCase,
)
from application.use_cases.inventory_use_cases import (
    ListCategoriesUseCase,
    ListSubCategoriesUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CategoryRepositoryImpl,
    SubCategoryRepositoryImpl,
    UserRepositoryImpl,
)
from presentation.serializers.business_serializers import (
    BusinessCreateSerializer,
    BusinessMemberCreateSerializer,
    BusinessMemberSerializer,
    BusinessResponseSerializer,
    BusinessUpdateSerializer,
)
from presentation.serializers.inventory_serializers import (
    CategoryResponseSerializer,
    SubCategoryResponseSerializer,
)
from shared.services import QRCodeService
from shared.views.base_viewset import BaseViewSet


class BusinessViewSet(BaseViewSet):
    """ViewSet for business management using DDD architecture."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List businesses",
        operation_description="Get all businesses for the authenticated user (owned or member).",
        responses={200: "List of businesses", 401: "Unauthorized"},
        tags=["Business"],
    )
    def list(self, request: Request) -> Response:
        """List all businesses for the authenticated user."""
        try:
            filter_payload = self.parse_list_filters(
                request,
                search_fields=["name", "unique_name"],
                order_fields=["name", "created_at", "updated_at"],
                filter_definitions={
                    "name": {"type": "string", "max_length": 255},
                    "is_active": {"type": "boolean"},
                },
            )
            filter_dto = BusinessListFilterDTO.from_payload(filter_payload)

            use_case = ListBusinessesUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
                user_id=request.user.id,
            )
            businesses = use_case.execute()

            if filter_dto.is_active is not None:
                businesses = [
                    business
                    for business in businesses
                    if business.is_active == filter_dto.is_active
                ]

            businesses = self.apply_filtering_to_items(
                businesses,
                filter_payload,
                name_fields=["name", "unique_name"],
            )

            business_member_repository = BusinessMemberRepositoryImpl()
            businesses_with_counts = []
            for business_dto in businesses:
                business_data = BusinessResponseSerializer.from_dto(
                    business_dto,
                    members=None,
                    member_count=None,
                )
                members = business_member_repository.get_business_members(
                    business_dto.id, active_only=True
                )
                business_data["member_count"] = len(members)
                businesses_with_counts.append(business_data)

            return self.paginated_response(
                request=request,
                queryset=businesses_with_counts,
                serializer_class=BusinessResponseSerializer,
                message="Businesses retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create business",
        operation_description="Create a new business. User becomes OWNER automatically.",
        request_body=BusinessCreateSerializer,
        responses={
            201: BusinessResponseSerializer,
            400: "Bad Request",
            401: "Unauthorized",
        },
        tags=["Business"],
    )
    def create(self, request: Request) -> Response:
        """Create a new business."""
        serializer = BusinessCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CreateBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
                owner_id=request.user.id,
            )
            business_dto = use_case.execute(dto)
            business_data = BusinessResponseSerializer.from_dto(business_dto)

            user = UserRepositoryImpl().get_by_id(request.user.id)

            business_data["user"] = {
                "id": str(user.id),
                "email": user.email or "",
                "name": user.name,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            }

            return self.success(
                message="Business created successfully. Your role has been updated to OWNER.",
                data=business_data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get business",
        operation_description="Get business details by ID.",
        responses={
            200: BusinessResponseSerializer,
            403: "Permission denied",
            404: "Business not found",
        },
        tags=["Business"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get business by ID."""
        try:
            business_domain_service = self._get_business_domain_service()
            use_case = GetBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=business_domain_service,
                business_id=pk,
                user_id=request.user.id,
            )
            business_dto = use_case.execute()

            members_use_case = ListBusinessMembersUseCase(
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=business_domain_service,
                user_repository=UserRepositoryImpl(),
                business_id=pk,
                user_id=request.user.id,
                include_inactive=False,
            )
            members = members_use_case.execute()

            business_data = BusinessResponseSerializer.from_dto(
                business_dto,
                members=members,
                member_count=len(members) if members else 0,
            )

            category_repository = CategoryRepositoryImpl()
            subcategory_repository = SubCategoryRepositoryImpl()

            categories_use_case = ListCategoriesUseCase(
                category_repository=category_repository,
                business_domain_service=business_domain_service,
                business_id=pk,
                user_id=request.user.id,
            )
            categories = categories_use_case.execute()
            categories_data: list[dict] = []

            for category_dto in categories:
                cat_data = CategoryResponseSerializer.from_dto(category_dto)
                subcategories_use_case = ListSubCategoriesUseCase(
                    subcategory_repository=subcategory_repository,
                    category_repository=category_repository,
                    business_domain_service=business_domain_service,
                    category_id=category_dto.id,
                    user_id=request.user.id,
                )
                subcategories = subcategories_use_case.execute()
                cat_data["subcategories"] = [
                    SubCategoryResponseSerializer.from_dto(sub_dto) for sub_dto in subcategories
                ]
                categories_data.append(cat_data)

            business_data["categories"] = categories_data

            return self.success(
                message="Business retrieved successfully",
                data=business_data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update business",
        operation_description="Update business details. Only owner and managers can update.",
        request_body=BusinessUpdateSerializer,
        responses={
            200: BusinessResponseSerializer,
            403: "Permission denied",
            404: "Business not found",
        },
        tags=["Business"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update business."""
        serializer = BusinessUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
            )
            business_dto = use_case.execute(dto)

            business_data = BusinessResponseSerializer.from_dto(business_dto)

            return self.success(
                message="Business updated successfully",
                data=business_data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete business",
        operation_description="Delete a business. Only owner can delete.",
        responses={200: "Business deleted", 403: "Permission denied", 404: "Business not found"},
        tags=["Business"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete business."""
        try:
            use_case = DeleteBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Business deleted successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Add business member",
        operation_description="Add a member to the business. Only owner and managers can add members.",
        request_body=BusinessMemberCreateSerializer,
        responses={
            201: BusinessMemberSerializer,
            400: "Validation error",
            403: "Permission denied",
        },
        tags=["Business"],
    )
    @action(detail=True, methods=["post"], url_path="members")
    def add_member(self, request: Request, pk: UUID) -> Response:
        """Add a member to the business."""
        serializer = BusinessMemberCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = AddBusinessMemberUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                user_repository=UserRepositoryImpl(),
                business_id=pk,
                user_id=request.user.id,
            )
            member_dto = use_case.execute(dto)

            member_data = BusinessMemberSerializer.from_dto(member_dto)

            user_created = not dto.user_id and (dto.email or dto.phone_number)

            message = "Business member added successfully"
            if user_created:
                message += ". Credentials have been sent to the member via email/SMS."

            return self.success(
                message=message,
                data=member_data,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        method="get",
        operation_summary="List business members",
        operation_description=(
            "List all members of a business with pagination support. Only users with access to "
            "the business can view members."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="page",
                in_=openapi.IN_QUERY,
                description="Page number (defaults to 1).",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name="page_size",
                in_=openapi.IN_QUERY,
                description="Number of records per page (defaults to 20, max 1000).",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name="include_inactive",
                in_=openapi.IN_QUERY,
                description="Include inactive members when set to true.",
                type=openapi.TYPE_BOOLEAN,
            ),
        ],
        responses={
            200: "List of business members",
            400: "Bad Request",
            403: "Permission denied",
            404: "Business not found",
        },
        tags=["Business"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="members/list",
        url_name="list-members",
    )
    def list_members(self, request: Request, pk: UUID) -> Response:
        """List members of the business."""
        try:
            filter_payload = self.parse_list_filters(
                request,
                search_fields=["user.name", "user.email"],
                order_fields=["joined_at", "role", "created_at"],
                default_order_field="joined_at",
                filter_definitions={
                    "include_inactive": {"type": "boolean"},
                    "role": {
                        "type": "enum",
                        "choices": ["owner", "manager", "cashier", "stock_keeper", "delivery"],
                    },
                    "name": {"type": "string", "max_length": 255},
                },
            )
            filter_payload["filters"]["business_id"] = pk
            filter_dto = BusinessMemberListFilterDTO.from_payload(filter_payload)

            use_case = ListBusinessMembersUseCase(
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                user_repository=UserRepositoryImpl(),
                business_id=pk,
                user_id=request.user.id,
                include_inactive=filter_dto.include_inactive,
            )
            members = use_case.execute()

            if filter_dto.role:
                members = [member for member in members if member.role == filter_dto.role]

            members = self.apply_filtering_to_items(
                members,
                filter_payload,
                name_fields=["user.name"],
            )

            return self.paginated_response(
                request=request,
                queryset=members,
                serializer_class=BusinessMemberSerializer,
                message="Business members retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Remove business member",
        operation_description="Remove a member from the business. Only owner and managers can remove members.",
        responses={200: "Member removed", 403: "Permission denied", 404: "Member not found"},
        tags=["Business"],
    )
    @action(detail=True, methods=["delete"], url_path="members/(?P<member_id>[^/.]+)")
    def remove_member(self, request: Request, pk: UUID, member_id: UUID) -> Response:
        """Remove a member from the business."""
        try:
            use_case = RemoveBusinessMemberUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_member_repository=BusinessMemberRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=pk,
                user_id=request.user.id,
            )
            use_case.execute(member_id)

            return self.success(
                message="Business member removed successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Scan QR code",
        operation_description="Scan QR code to get business information.",
        request_body=None,
        responses={
            200: BusinessResponseSerializer,
            400: "Invalid QR code",
            404: "Business not found",
        },
        tags=["Business"],
    )
    @action(detail=False, methods=["post"], url_path="scan-qr")
    def scan_qr_code(self, request: Request) -> Response:
        """Scan QR code to get business information."""
        try:
            qr_data = request.data.get("qr_data") or request.data.get("qr_code")
            if not qr_data:
                return self.error(
                    message="QR code data is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_QR_DATA",
                )

            qr_service = QRCodeService()
            parsed_data = qr_service.scan_qr_code(qr_data)

            business_id = parsed_data["business_id"]

            # Get business details
            use_case = GetBusinessUseCase(
                business_repository=BusinessRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            business_dto = use_case.execute()

            business_data = BusinessResponseSerializer.from_dto(business_dto)

            return self.success(
                message="Business retrieved from QR code",
                data=business_data,
                status_code=status.HTTP_200_OK,
            )
        except ValueError as e:
            return self.error(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_QR_CODE",
            )
        except Exception as e:
            return self.handle_exception(e)
