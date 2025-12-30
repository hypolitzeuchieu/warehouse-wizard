"""Category ViewSet for category management."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.inventory_use_cases import (
    DeleteCategoryUseCase,
    GetCategoryUseCase,
    ListCategoriesUseCase,
    UpdateCategoryUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CategoryRepositoryImpl,
)
from presentation.serializers.business_serializers import BusinessIdQuerySerializer
from presentation.serializers.inventory_serializers import (
    CategoryResponseSerializer,
    CategoryUpdateSerializer,
)
from shared.permissions.business_permissions import IsBusinessActive
from shared.views.base_viewset import BaseViewSet


class CategoryViewSet(BaseViewSet):
    """ViewSet for category management."""

    permission_classes = [IsAuthenticated, IsBusinessActive]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List categories",
        operation_description="List all categories for a business.",
        query_serializer=BusinessIdQuerySerializer,
        responses={
            200: CategoryResponseSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal Server Error",
        },
        tags=["Inventory - Categories"],
    )
    def list(self, request: Request) -> Response:
        """List all categories for a business."""
        try:
            query_serializer = BusinessIdQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]

            filter_payload = self.parse_list_filters(
                request,
                search_fields=["name"],
                order_fields=["name", "created_at", "updated_at"],
                filter_definitions={
                    "name": {"type": "string", "max_length": 100},
                },
                additional_allowed_params=["business_id"],
            )

            use_case = ListCategoriesUseCase(
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            categories = use_case.execute()

            categories = self.apply_filtering_to_items(
                categories,
                filter_payload,
                name_fields=["name"],
            )

            return self.paginated_response(
                request=request,
                queryset=categories,
                serializer_class=CategoryResponseSerializer,
                message="Categories retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get category",
        operation_description="Get category details by ID.",
        operation_id="category_retrieve",
        responses={
            200: CategoryResponseSerializer(),
            403: "Permission denied",
            404: "Category not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - Categories"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get category by ID."""
        try:
            use_case = GetCategoryUseCase(
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                category_id=pk,
                user_id=request.user.id,
            )
            category_dto = use_case.execute()
            return self.success(
                message="Category retrieved successfully",
                data=CategoryResponseSerializer.from_dto(category_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update category",
        operation_description="Update category details.",
        operation_id="category_update",
        request_body=CategoryUpdateSerializer,
        responses={
            200: CategoryResponseSerializer(),
            403: "Permission denied",
            404: "Not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - Categories"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update a category."""
        serializer = CategoryUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateCategoryUseCase(
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                category_id=pk,
                user_id=request.user.id,
            )
            category_dto = use_case.execute(dto)
            return self.success(
                message="Category updated successfully",
                data=CategoryResponseSerializer.from_dto(category_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete category",
        operation_description="Delete a category.",
        operation_id="category_destroy",
        responses={
            204: "Category deleted successfully",
            403: "Permission denied",
            404: "Category not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - Categories"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete a category."""
        try:
            use_case = DeleteCategoryUseCase(
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                category_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()
            return self.success(
                message="Category deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return self.handle_exception(e)
