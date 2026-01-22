"""Product ViewSet for product management."""

from __future__ import annotations

from uuid import UUID

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.product_list_filter_dto import ProductListFilterDTO
from application.use_cases.inventory_use_cases import (
    CreateProductUseCase,
    DeleteProductUseCase,
    GetProductUseCase,
    ListProductsUseCase,
    UpdateProductUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CategoryRepositoryImpl,
    ProductRepositoryImpl,
    SubCategoryRepositoryImpl,
)
from presentation.serializers.inventory_serializers import (
    ProductCreateSerializer,
    ProductListQuerySerializer,
    ProductResponseSerializer,
    ProductScanSerializer,
    ProductUpdateSerializer,
)
from shared.exceptions.specific import BadRequestError, NotFoundError
from shared.views.base_viewset import BaseViewSet


class ProductViewSet(BaseViewSet):
    """ViewSet for product management."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    def _list_products_for_scope(
        self,
        request: Request,
        *,
        business_id: UUID,
        category_id: UUID | None = None,
        subcategory_id: UUID | None = None,
    ) -> Response:
        """List products for a given scope."""
        filter_payload = self.parse_list_filters(
            request,
            search_fields=["name", "barcode"],
            order_fields=[
                "name",
                "created_at",
                "updated_at",
                "quantity",
                "unit_price",
            ],
            filter_definitions={
                "name": {"type": "string", "max_length": 255},
                "category_id": {"type": "uuid"},
                "subcategory_id": {"type": "uuid"},
                "low_stock_only": {"type": "boolean"},
                "expired_only": {"type": "boolean"},
            },
            additional_allowed_params=["business_id"],
        )
        filter_payload["filters"]["business_id"] = str(business_id)
        if category_id is not None:
            filter_payload["filters"]["category_id"] = str(category_id)
        if subcategory_id is not None:
            filter_payload["filters"]["subcategory_id"] = (
                str(subcategory_id) if subcategory_id else None
            )

        filter_dto = ProductListFilterDTO.from_payload(filter_payload)
        resolved_category_id = category_id or filter_dto.category_id
        resolved_subcategory_id = (
            subcategory_id if subcategory_id is not None else filter_dto.subcategory_id
        )

        def _to_uuid(value: UUID | str | None) -> UUID | None:
            if value is None:
                return None
            if isinstance(value, UUID):
                return value
            return UUID(str(value))

        category_repo = CategoryRepositoryImpl()
        subcategory_repo = SubCategoryRepositoryImpl()

        resolved_category_uuid = _to_uuid(resolved_category_id)
        resolved_subcategory_uuid = _to_uuid(resolved_subcategory_id)

        category_obj = None
        if resolved_category_uuid:
            category_obj = category_repo.get_by_id(resolved_category_uuid)
            if not category_obj or category_obj.business_id != business_id:
                raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

        if resolved_subcategory_uuid:
            subcategory_obj = subcategory_repo.get_by_id(resolved_subcategory_uuid)
            if not subcategory_obj or subcategory_obj.business_id != business_id:
                raise NotFoundError(
                    detail="Subcategory not found",
                    code="SUBCATEGORY_NOT_FOUND",
                )
            if category_obj and subcategory_obj.category_id != category_obj.id:
                raise BadRequestError(
                    detail="Subcategory does not belong to the selected category",
                    code="SUBCATEGORY_MISMATCH",
                )
            if category_obj is None:
                resolved_category_uuid = subcategory_obj.category_id
                category_obj = category_repo.get_by_id(resolved_category_uuid)

        if resolved_category_uuid:
            filter_payload["filters"]["category_id"] = str(resolved_category_uuid)
        if resolved_subcategory_uuid is not None:
            filter_payload["filters"]["subcategory_id"] = (
                str(resolved_subcategory_uuid) if resolved_subcategory_uuid else None
            )

        use_case = ListProductsUseCase(
            product_repository=ProductRepositoryImpl(),
            business_domain_service=self._get_business_domain_service(),
            business_id=business_id,
            user_id=request.user.id,
            category_id=resolved_category_uuid,
            subcategory_id=resolved_subcategory_uuid,
            low_stock_only=filter_dto.low_stock_only,
            expired_only=filter_dto.expired_only,
        )
        products = use_case.execute()
        products = self.apply_filtering_to_items(
            products,
            filter_payload,
            name_fields=["name", "barcode"],
        )

        return self.paginated_response(
            request=request,
            queryset=products,
            serializer_class=ProductResponseSerializer,
            message="Products retrieved successfully",
        )

    @swagger_auto_schema(
        operation_summary="List products by category",
        operation_description="List all products belonging to a specific category.",
        operation_id="product_list_by_category",
        responses={
            200: ProductResponseSerializer(many=True),
            403: "Permission denied",
            404: "Category not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="categories/(?P<category_id>[^/.]+)/products",
        url_name="category-products",
    )
    def list_products_by_category(self, request: Request, category_id: UUID) -> Response:
        """List products for a category."""
        try:
            category = CategoryRepositoryImpl().get_by_id(category_id)
            if not category:
                raise NotFoundError(detail="Category not found", code="CATEGORY_NOT_FOUND")

            return self._list_products_for_scope(
                request,
                business_id=category.business_id,
                category_id=category.id,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="List products by subcategory",
        operation_description="List all products belonging to a specific subcategory.",
        operation_id="product_list_by_subcategory",
        responses={
            200: ProductResponseSerializer(many=True),
            403: "Permission denied",
            404: "Subcategory not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="subcategories/(?P<subcategory_id>[^/.]+)/products",
        url_name="subcategory-products",
    )
    def list_products_by_subcategory(self, request: Request, subcategory_id: UUID) -> Response:
        """List products for a subcategory."""
        try:
            if not isinstance(subcategory_id, UUID):
                try:
                    subcategory_id = UUID(str(subcategory_id))
                except (ValueError, TypeError):
                    raise NotFoundError(
                        detail="Invalid subcategory ID format",
                        code="SUBCATEGORY_NOT_FOUND",
                    ) from None

            subcategory = SubCategoryRepositoryImpl().get_by_id(subcategory_id)
            if not subcategory:
                raise NotFoundError(
                    detail="Subcategory not found",
                    code="SUBCATEGORY_NOT_FOUND",
                )

            return self._list_products_for_scope(
                request,
                business_id=subcategory.business_id,
                category_id=subcategory.category_id,
                subcategory_id=subcategory.id,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="List products",
        operation_description="Get all products for a business with optional filters.",
        operation_id="product_list",
        query_serializer=ProductListQuerySerializer,
        responses={
            200: ProductResponseSerializer(many=True),
            403: "Permission denied",
            404: "Business not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    def list(self, request: Request) -> Response:
        """List all products for a business."""
        try:
            # Validate query parameters
            query_serializer = ProductListQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]

            return self._list_products_for_scope(
                request,
                business_id=business_id,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create product",
        operation_description="Create a new product for a business. business_id must be provided in the request body.",
        operation_id="product_create",
        request_body=ProductCreateSerializer,
        responses={
            201: ProductResponseSerializer(),
            400: "Validation error",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    def create(self, request: Request) -> Response:
        """Create a new product."""
        # Merge files into data for serializer
        data = request.data.copy()
        if request.FILES:
            data.update(request.FILES)

        serializer = ProductCreateSerializer(data=data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            # Get business_id from serializer validated data
            business_id_str = serializer.validated_data.get("business_id")
            if not business_id_str:
                return self.error(
                    message="business_id is required in request body",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BUSINESS_ID",
                )

            try:
                business_id = UUID(str(business_id_str))
            except (ValueError, TypeError):
                return self.error(
                    message="Invalid business_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_BUSINESS_ID",
                )

            dto = serializer.to_dto(business_id=str(business_id))
            use_case = CreateProductUseCase(
                product_repository=ProductRepositoryImpl(),
                category_repository=CategoryRepositoryImpl(),
                subcategory_repository=SubCategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute(dto)

            return self.success(
                message="Product created successfully",
                data=ProductResponseSerializer.from_dto(product_dto),
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get product",
        operation_description="Get product details by ID. business_id is retrieved from the product.",
        operation_id="product_retrieve",
        responses={
            200: ProductResponseSerializer(),
            403: "Permission denied",
            404: "Product not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get product by ID."""
        try:
            # Get product first to retrieve business_id
            product_repo = ProductRepositoryImpl()
            product = product_repo.get_by_id(pk)
            if not product:
                return self.error(
                    message="Product not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="PRODUCT_NOT_FOUND",
                )

            use_case = GetProductUseCase(
                product_repository=product_repo,
                business_domain_service=self._get_business_domain_service(),
                product_id=pk,
                business_id=product.business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute()

            return self.success(
                message="Product retrieved successfully",
                data=ProductResponseSerializer.from_dto(product_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update product",
        operation_description="Update product details with full update (PUT). All fields should be provided. business_id is retrieved from the product.",
        operation_id="product_update",
        request_body=ProductUpdateSerializer,
        responses={
            200: ProductResponseSerializer(),
            403: "Permission denied",
            404: "Product not found",
            400: "Validation error",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update product (PUT)."""
        product_repo = ProductRepositoryImpl()
        existing_product = product_repo.get_by_id(pk)
        if not existing_product:
            return self.error(
                message="Product not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="PRODUCT_NOT_FOUND",
            )

        old_image_url = existing_product.image_url
        business_id = existing_product.business_id

        # Merge files into data for serializer
        data = request.data.copy()
        if request.FILES:
            data.update(request.FILES)

        serializer = ProductUpdateSerializer(data=data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto(business_id=str(business_id), old_image_url=old_image_url)
            use_case = UpdateProductUseCase(
                product_repository=product_repo,
                category_repository=CategoryRepositoryImpl(),
                subcategory_repository=SubCategoryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                product_id=pk,
                business_id=business_id,
                user_id=request.user.id,
            )
            product_dto = use_case.execute(dto)

            return self.success(
                message="Product updated successfully",
                data=ProductResponseSerializer.from_dto(product_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete product",
        operation_description="Delete a product. business_id is retrieved from the product.",
        operation_id="product_destroy",
        responses={
            204: "Product deleted successfully",
            403: "Permission denied",
            404: "Product not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete product."""
        try:
            # Get product first to retrieve business_id
            product_repo = ProductRepositoryImpl()
            product = product_repo.get_by_id(pk)
            if not product:
                return self.error(
                    message="Product not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="PRODUCT_NOT_FOUND",
                )

            use_case = DeleteProductUseCase(
                product_repository=product_repo,
                business_domain_service=self._get_business_domain_service(),
                product_id=pk,
                business_id=product.business_id,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Product deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Scan barcode",
        operation_description="Scan barcode to get product information. Falls back to product ID if barcode not found. business_id is required in request body.",
        operation_id="product_scan_barcode",
        request_body=ProductScanSerializer,
        responses={
            200: ProductScanSerializer(),
            400: "Validation error",
            403: "Permission denied",
            404: "Product not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="scan-barcode",
        url_name="scan-barcode",
    )
    def scan_barcode(self, request: Request) -> Response:
        """Scan barcode to get product information."""
        try:
            barcode = request.data.get("barcode")
            product_id = request.data.get("product_id")  # Fallback option
            business_id_str = request.data.get("business_id")

            if not business_id_str:
                return self.error(
                    message="business_id is required in request body",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BUSINESS_ID",
                )

            try:
                business_id = UUID(business_id_str)
            except (ValueError, TypeError):
                return self.error(
                    message="Invalid business_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_BUSINESS_ID",
                )

            if not barcode and not product_id:
                return self.error(
                    message="Barcode or product_id is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BARCODE_OR_ID",
                )

            product_repository = ProductRepositoryImpl()

            # Try to find by barcode first
            product = None
            if barcode:
                product = product_repository.get_by_barcode(barcode, business_id)

            # Fallback to product ID if barcode not found
            if not product and product_id:
                try:
                    product = product_repository.get_by_id(UUID(product_id))
                    if product and product.business_id != business_id:
                        product = None
                except (ValueError, TypeError):
                    pass

            if not product:
                return self.error(
                    message="Product not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="PRODUCT_NOT_FOUND",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            return self.success(
                message="Product retrieved successfully",
                data=ProductScanSerializer.from_product(product),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Scan barcode (GET)",
        operation_description="Scan barcode via GET request. Simpler for some scanner configurations. business_id is required as query parameter.",
        operation_id="product_scan_barcode_get",
        manual_parameters=[
            openapi.Parameter(
                "barcode",
                openapi.IN_PATH,
                description="Barcode to scan",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "business_id",
                openapi.IN_QUERY,
                description="Business ID (required)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            ),
        ],
        responses={
            200: ProductScanSerializer(),
            400: "Validation error",
            403: "Permission denied",
            404: "Product not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Products"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="scan-barcode/(?P<barcode>[^/.]+)",
        url_name="scan-barcode-get",
    )
    def scan_barcode_get(self, request: Request, barcode: str) -> Response:
        """Scan barcode via GET request (simpler for some scanner configurations)."""
        try:
            if not barcode:
                return self.error(
                    message="Barcode is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BARCODE",
                )

            business_id_str = request.query_params.get("business_id")
            if not business_id_str:
                return self.error(
                    message="business_id query parameter is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BUSINESS_ID",
                )

            try:
                business_id = UUID(business_id_str)
            except (ValueError, TypeError):
                return self.error(
                    message="Invalid business_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_BUSINESS_ID",
                )

            product_repository = ProductRepositoryImpl()

            # Find product by barcode
            product = product_repository.get_by_barcode(barcode, business_id)

            if not product:
                return self.error(
                    message="Product not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="PRODUCT_NOT_FOUND",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            return self.success(
                message="Product retrieved successfully",
                data=ProductScanSerializer.from_product(product),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
