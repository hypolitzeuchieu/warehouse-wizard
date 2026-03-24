"""SubCategory ViewSet for subcategory management."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.inventory_use_cases import (
    DeleteSubCategoryUseCase,
    GetSubCategoryUseCase,
    UpdateSubCategoryUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CategoryRepositoryImpl,
    SubCategoryRepositoryImpl,
)
from presentation.serializers.inventory_serializers import (
    SubCategoryResponseSerializer,
    SubCategoryUpdateSerializer,
)
from shared.views.base_viewset import BaseViewSet


class SubCategoryViewSet(BaseViewSet):
    """ViewSet for subcategory management."""

    permission_classes = [IsAuthenticated]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="Get subcategory",
        operation_description="Get subcategory details by ID.",
        operation_id="subcategory_retrieve",
        responses={
            200: SubCategoryResponseSerializer(),
            403: "Permission denied",
            404: "Subcategory not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - SubCategories"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get subcategory by ID."""
        try:
            use_case = GetSubCategoryUseCase(
                subcategory_repository=SubCategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                subcategory_id=pk,
                user_id=request.user.id,
            )
            subcategory_dto = use_case.execute()
            return self.success(
                message="Subcategory retrieved successfully",
                data=SubCategoryResponseSerializer.from_dto(subcategory_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update subcategory",
        operation_description="Update subcategory details.",
        operation_id="subcategory_update",
        request_body=SubCategoryUpdateSerializer,
        responses={
            200: SubCategoryResponseSerializer(),
            403: "Permission denied",
            404: "Subcategory not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - SubCategories"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update subcategory."""
        serializer = SubCategoryUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateSubCategoryUseCase(
                subcategory_repository=SubCategoryRepositoryImpl(),
                category_repository=CategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                subcategory_id=pk,
                user_id=request.user.id,
            )
            subcategory_dto = use_case.execute(dto)
            return self.success(
                message="Subcategory updated successfully",
                data=SubCategoryResponseSerializer.from_dto(subcategory_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete subcategory",
        operation_description="Delete a subcategory.",
        operation_id="subcategory_destroy",
        responses={
            204: "Subcategory deleted successfully",
            403: "Permission denied",
            404: "Subcategory not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Inventory - SubCategories"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete subcategory."""
        try:
            use_case = DeleteSubCategoryUseCase(
                subcategory_repository=SubCategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                subcategory_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()
            return self.success(
                message="Subcategory deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return self.handle_exception(e)
