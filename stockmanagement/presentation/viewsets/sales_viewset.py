"""Sales ViewSet for invoices and orders."""

from __future__ import annotations

import json
from uuid import UUID

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.invoice_list_filter_dto import InvoiceListFilterDTO
from application.dto.sales_dto import PaymentResponseDTO
from application.use_cases.sales_use_cases import (
    ApplyCreditToInvoiceUseCase,
    CancelInvoiceUseCase,
    CreateInvoiceUseCase,
    GetInvoiceUseCase,
    ListInvoicesUseCase,
    PayInvoiceUseCase,
    ProcessRefundUseCase,
    ScanBarcodeForSaleUseCase,
    SearchProductsForSaleUseCase,
    UpdateInvoiceUseCase,
)
from domain.business.services import BusinessDomainService
from domain.inventory.services import InventoryDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CreditRepositoryImpl,
    CustomerRepositoryImpl,
    InvoiceLineRepositoryImpl,
    InvoiceLogRepositoryImpl,
    InvoicePaymentRepositoryImpl,
    InvoiceRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
)
from presentation.serializers.sales_serializers import (
    BarcodeScanResponseSerializer,
    BarcodeScanSerializer,
    CreditApplicationSerializer,
    InvoiceCreateSerializer,
    InvoiceListQuerySerializer,
    InvoiceResponseSerializer,
    InvoiceUpdateSerializer,
    PaymentCreateSerializer,
    PaymentProcessedResponseSerializer,
    PaymentResponseSerializer,
    ProductSearchResponseSerializer,
    ProductSearchSerializer,
    RefundCreateSerializer,
    RefundResponseSerializer,
)
from shared.security.query_params_validator import QueryParamsValidator
from shared.views.base_viewset import BaseViewSet


class SalesViewSet(BaseViewSet):
    """ViewSet for sales management (invoices and orders)."""

    permission_classes = [IsAuthenticated]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    def _get_inventory_domain_service(self) -> InventoryDomainService:
        """Get inventory domain service instance."""
        return InventoryDomainService(
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List invoices",
        operation_description="Get all invoices for a business with optional filters.",
        query_serializer=InvoiceListQuerySerializer,
        responses={
            200: InvoiceResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Sales"],
    )
    def list(self, request: Request) -> Response:
        """List all invoices for a business."""
        try:
            # Validate query parameters
            query_serializer = InvoiceListQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]

            filter_payload = self.parse_list_filters(
                request,
                search_fields=["customer_name", "cashier_name", "number"],
                order_fields=["created_at", "updated_at", "total", "number"],
                filter_definitions={
                    "status": {
                        "type": "enum",
                        "choices": ["PENDING", "PAID", "PARTIAL", "CANCELLED", "REFUNDED"],
                    },
                    "start_date": {"type": "date"},
                    "end_date": {"type": "date"},
                },
                additional_allowed_params=["business_id"],
            )
            filter_payload["filters"]["business_id"] = business_id
            filter_dto = InvoiceListFilterDTO.from_payload(filter_payload)

            use_case = ListInvoicesUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                status=filter_dto.status,
                start_date=filter_dto.start_date,
                end_date=filter_dto.end_date,
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
            )
            invoices = use_case.execute()

            invoices = self.apply_filtering_to_items(
                invoices,
                filter_payload,
                name_fields=["customer_name", "cashier_name"],
            )

            return self.paginated_response(
                request=request,
                queryset=invoices,
                serializer_class=InvoiceResponseSerializer,
                message="Invoices retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create invoice",
        operation_description="Create a new invoice (POS). business_id must be provided in the request body.",
        request_body=InvoiceCreateSerializer,
        responses={201: "Invoice created", 400: "Bad Request", 403: "Permission denied"},
        tags=["Sales"],
    )
    def create(self, request: Request) -> Response:
        """Create a new invoice."""
        serializer = InvoiceCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            business_id = serializer.validated_data.get("business_id")
            if not business_id:
                return self.error(
                    message="business_id is required in request body",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BUSINESS_ID",
                )

            dto = serializer.to_dto()

            use_case = CreateInvoiceUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                invoice_payment_repository=InvoicePaymentRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                credit_repository=CreditRepositoryImpl(),
                customer_repository=CustomerRepositoryImpl(),
                business_id=business_id,
                cashier_id=request.user.id,
            )
            invoice_dto = use_case.execute(dto)

            return self.success(
                message="Invoice created successfully",
                data={
                    "id": str(invoice_dto.id),
                    "business_id": str(invoice_dto.business_id),
                    "number": invoice_dto.number,
                    "customer_name": invoice_dto.customer_name,
                    "customer_id": (
                        str(invoice_dto.customer_id) if invoice_dto.customer_id else None
                    ),
                    "cashier_id": str(invoice_dto.cashier_id),
                    "status": invoice_dto.status,
                    "total": str(invoice_dto.total),
                    "tax": str(invoice_dto.tax),
                    "discount": str(invoice_dto.discount),
                    "advance_paid": str(invoice_dto.advance_paid),
                    "remaining_amount": str(invoice_dto.remaining_amount),
                    "payment_method": invoice_dto.payment_method,
                    "due_date": invoice_dto.due_date.isoformat() if invoice_dto.due_date else None,
                    "is_credit_settled": invoice_dto.is_credit_settled,
                    "reason": invoice_dto.reason,
                    "lines": [
                        {
                            "id": str(line.id),
                            "product_id": str(line.product_id),
                            "quantity": line.quantity,
                            "unit_price": str(line.unit_price),
                            "discount": str(line.discount),
                            "line_total": str(line.line_total),
                            "created_at": line.created_at.isoformat(),
                        }
                        for line in (invoice_dto.lines or [])
                    ],
                    "created_at": invoice_dto.created_at.isoformat(),
                    "updated_at": invoice_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get invoice",
        operation_description="Get invoice details by ID. business_id is retrieved from the invoice.",
        responses={
            200: InvoiceResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Invoice not found",
        },
        tags=["Sales"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get invoice by ID."""
        try:
            use_case = GetInvoiceUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_id=pk,
            )
            invoice_dto = use_case.execute()

            # Verify user has access to the business
            if not self._get_business_domain_service().user_has_access(
                invoice_dto.business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            return self.success(
                message="Invoice retrieved successfully",
                data={
                    "id": str(invoice_dto.id),
                    "business_id": str(invoice_dto.business_id),
                    "number": invoice_dto.number,
                    "customer_name": invoice_dto.customer_name,
                    "customer_id": (
                        str(invoice_dto.customer_id) if invoice_dto.customer_id else None
                    ),
                    "cashier_id": str(invoice_dto.cashier_id),
                    "status": invoice_dto.status,
                    "total": str(invoice_dto.total),
                    "tax": str(invoice_dto.tax),
                    "discount": str(invoice_dto.discount),
                    "advance_paid": str(invoice_dto.advance_paid),
                    "remaining_amount": str(invoice_dto.remaining_amount),
                    "payment_method": invoice_dto.payment_method,
                    "due_date": invoice_dto.due_date.isoformat() if invoice_dto.due_date else None,
                    "is_credit_settled": invoice_dto.is_credit_settled,
                    "reason": invoice_dto.reason,
                    "lines": [
                        {
                            "id": str(line.id),
                            "product_id": str(line.product_id),
                            "quantity": line.quantity,
                            "unit_price": str(line.unit_price),
                            "discount": str(line.discount),
                            "line_total": str(line.line_total),
                            "created_at": line.created_at.isoformat(),
                        }
                        for line in (invoice_dto.lines or [])
                    ],
                    "created_at": invoice_dto.created_at.isoformat(),
                    "updated_at": invoice_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update invoice",
        operation_description="Update an existing invoice with full update.",
        request_body=InvoiceUpdateSerializer,
        responses={
            200: InvoiceResponseSerializer(),
            400: "Validation error",
            403: "Permission denied",
            404: "Invoice not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Sales"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update an invoice."""
        # Get invoice first to retrieve business_id
        invoice_repo = InvoiceRepositoryImpl()
        invoice = invoice_repo.get_by_id(pk)
        if not invoice:
            return self.error(
                message="Invoice not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="INVOICE_NOT_FOUND",
            )

        serializer = InvoiceUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateInvoiceUseCase(
                invoice_repository=invoice_repo,
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            invoice_dto = use_case.execute(dto)

            return self.success(
                message="Invoice updated successfully",
                data=InvoiceResponseSerializer.from_dto(invoice_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete invoice",
        operation_description="Delete (cancel) an invoice. This will cancel the invoice, restore stock, and cancel associated credits. business_id is retrieved from the invoice.",
        responses={
            200: "Invoice deleted",
            400: "Validation error",
            403: "Permission denied",
            404: "Invoice not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Sales"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete (cancel) an invoice."""
        try:
            # Get invoice first to verify it exists
            invoice_repo = InvoiceRepositoryImpl()
            invoice = invoice_repo.get_by_id(pk)
            if not invoice:
                return self.error(
                    message="Invoice not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
                )

            # Get reason from request body if provided
            reason = None
            if hasattr(request, "data") and request.data:
                reason = request.data.get("reason")
            elif hasattr(request, "body") and request.body:
                try:
                    body_data = json.loads(request.body)
                    reason = body_data.get("reason")
                except (json.JSONDecodeError, AttributeError):
                    pass

            use_case = CancelInvoiceUseCase(
                invoice_repository=invoice_repo,
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                credit_repository=CreditRepositoryImpl(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            invoice_dto = use_case.execute(reason=reason)

            return self.success(
                message="Invoice deleted successfully",
                data=InvoiceResponseSerializer.from_dto(invoice_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Cancel invoice",
        operation_description="Cancel an invoice and restore stock. business_id is retrieved from the invoice.",
        responses={
            200: InvoiceResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Invoice not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path="cancel",
    )
    def cancel_invoice(self, request: Request, pk: UUID) -> Response:
        """Cancel an invoice."""
        try:
            # Get invoice first to verify it exists
            invoice_repo = InvoiceRepositoryImpl()
            invoice = invoice_repo.get_by_id(pk)
            if not invoice:
                return self.error(
                    message="Invoice not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
                )

            reason = request.data.get("reason") if hasattr(request, "data") else None
            use_case = CancelInvoiceUseCase(
                invoice_repository=invoice_repo,
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                credit_repository=CreditRepositoryImpl(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            invoice_dto = use_case.execute(reason=reason)

            return self.success(
                message="Invoice cancelled successfully",
                data=InvoiceResponseSerializer.from_dto(invoice_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Process payment",
        operation_description="Process a payment for an invoice. business_id is retrieved from the invoice.",
        request_body=PaymentCreateSerializer,
        responses={
            200: PaymentProcessedResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Invoice not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="payments",
    )
    def pay_invoice(self, request: Request, pk: UUID) -> Response:
        """Process a payment for an invoice."""
        serializer = PaymentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            # Get invoice first to verify it exists
            invoice_repo = InvoiceRepositoryImpl()
            invoice = invoice_repo.get_by_id(pk)
            if not invoice:
                return self.error(
                    message="Invoice not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
                )

            dto = serializer.to_dto()
            use_case = PayInvoiceUseCase(
                invoice_repository=invoice_repo,
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_payment_repository=InvoicePaymentRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                credit_repository=CreditRepositoryImpl(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            invoice_dto, payment_dto = use_case.execute(dto)

            return self.success(
                message="Payment processed successfully",
                data={
                    "invoice": InvoiceResponseSerializer.from_dto(invoice_dto),
                    "payment": PaymentResponseSerializer.from_dto(payment_dto),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Process refund",
        operation_description="Process a refund for an invoice. business_id is retrieved from the invoice.",
        request_body=RefundCreateSerializer,
        responses={
            200: RefundResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Invoice not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="refunds",
    )
    def refund_invoice(self, request: Request, pk: UUID) -> Response:
        """Process a refund for an invoice."""
        serializer = RefundCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            # Get invoice first to verify it exists
            invoice_repo = InvoiceRepositoryImpl()
            invoice = invoice_repo.get_by_id(pk)
            if not invoice:
                return self.error(
                    message="Invoice not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
                )

            dto = serializer.to_dto()
            use_case = ProcessRefundUseCase(
                invoice_repository=invoice_repo,
                invoice_payment_repository=InvoicePaymentRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            refund_dto = use_case.execute(dto)

            return self.success(
                message="Refund processed successfully",
                data=RefundResponseSerializer.from_dto(refund_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get invoice payments",
        operation_description="Get payment history for an invoice. business_id is retrieved from the invoice.",
        responses={
            200: PaymentResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
            404: "Invoice not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="payments",
    )
    def get_invoice_payments(self, request: Request, pk: UUID) -> Response:
        """Get payment history for an invoice."""
        try:
            # Verify invoice exists
            invoice_repo = InvoiceRepositoryImpl()
            invoice = invoice_repo.get_by_id(pk)
            if not invoice:
                return self.error(
                    message="Invoice not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
                )

            payments = InvoicePaymentRepositoryImpl().get_by_invoice(pk)
            payment_dtos = [
                PaymentResponseDTO(
                    id=p.id,
                    invoice_id=p.invoice_id,
                    amount=p.amount,
                    payment_method=p.payment_method.value,
                    change_amount=p.change_amount,
                    refund_amount=p.refund_amount,
                    payment_date=p.payment_date,
                    notes=p.notes,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                    created_by=p.created_by,
                )
                for p in payments
            ]

            return self.success(
                message="Payments retrieved successfully",
                data=[PaymentResponseSerializer.from_dto(p) for p in payment_dtos],
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Apply credit to invoice",
        operation_description="Apply a credit to an invoice. business_id is retrieved from the invoice.",
        request_body=CreditApplicationSerializer,
        responses={
            200: InvoiceResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Invoice or credit not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="apply-credit",
    )
    def apply_credit_to_invoice(self, request: Request, pk: UUID) -> Response:
        """Apply a credit to an invoice."""
        serializer = CreditApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            # Get invoice first to verify it exists
            invoice_repo = InvoiceRepositoryImpl()
            invoice = invoice_repo.get_by_id(pk)
            if not invoice:
                return self.error(
                    message="Invoice not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
                )

            dto = serializer.to_dto()
            use_case = ApplyCreditToInvoiceUseCase(
                invoice_repository=invoice_repo,
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                credit_repository=CreditRepositoryImpl(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            invoice_dto = use_case.execute(dto)

            return self.success(
                message="Credit applied successfully",
                data=InvoiceResponseSerializer.from_dto(invoice_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Search products for sale",
        operation_description="Search products for sale (POS). business_id is required as query parameter.",
        manual_parameters=[
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
            200: ProductSearchResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Sales"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="products/search",
    )
    def search_products_for_sale(self, request: Request) -> Response:
        """Search products for sale."""
        try:
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

            serializer = ProductSearchSerializer(data=request.query_params)
            if not serializer.is_valid():
                return self.handle_validation_error(serializer)

            query = serializer.validated_data["query"]
            limit = serializer.validated_data.get("limit", 20)

            use_case = SearchProductsForSaleUseCase(
                product_repository=ProductRepositoryImpl(),
                business_id=business_id,
            )
            products = use_case.execute(query=query, limit=limit)

            return self.success(
                message="Products retrieved successfully",
                data=[ProductSearchResponseSerializer.from_dto(p) for p in products],
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Scan barcode for sale",
        operation_description="Scan a barcode to get product information for sale. business_id must be provided in the request body.",
        request_body=BarcodeScanSerializer,
        responses={
            200: BarcodeScanResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Product not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="products/scan",
    )
    def scan_barcode_for_sale(self, request: Request) -> Response:
        """Scan a barcode to get product information."""
        serializer = BarcodeScanSerializer(data=request.data)
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

            barcode = serializer.validated_data["barcode"]
            use_case = ScanBarcodeForSaleUseCase(
                product_repository=ProductRepositoryImpl(),
                business_id=business_id,
            )
            product_dto = use_case.execute(barcode=barcode)

            return self.success(
                message="Product retrieved successfully",
                data=BarcodeScanResponseSerializer.from_dto(product_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
