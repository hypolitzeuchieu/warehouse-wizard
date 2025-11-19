"""Sales ViewSet for invoices and orders."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.invoice_list_filter_dto import InvoiceListFilterDTO
from application.use_cases.sales_use_cases import (
    CreateInvoiceUseCase,
    GetInvoiceUseCase,
    ListInvoicesUseCase,
)
from domain.business.services import BusinessDomainService
from domain.inventory.services import InventoryDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    InvoiceLineRepositoryImpl,
    InvoiceRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
)
from presentation.serializers.sales_serializers import (
    InvoiceCreateSerializer,
    InvoiceResponseSerializer,
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
        responses={200: "List of invoices", 403: "Permission denied"},
        tags=["Sales"],
    )
    @action(detail=False, methods=["get"], url_path="businesses/(?P<business_id>[^/.]+)/invoices")
    def list_invoices(self, request: Request, business_id: UUID) -> Response:
        """List all invoices for a business."""
        try:
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
        operation_description="Create a new invoice (POS).",
        request_body=InvoiceCreateSerializer,
        responses={201: "Invoice created", 400: "Validation error", 403: "Permission denied"},
        tags=["Sales"],
    )
    @action(detail=False, methods=["post"], url_path="businesses/(?P<business_id>[^/.]+)/invoices")
    def create_invoice(self, request: Request, business_id: UUID) -> Response:
        """Create a new invoice."""
        serializer = InvoiceCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CreateInvoiceUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
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
        operation_description="Get invoice details by ID.",
        responses={200: "Invoice details", 403: "Permission denied", 404: "Invoice not found"},
        tags=["Sales"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/invoices/(?P<invoice_id>[^/.]+)",
    )
    def get_invoice(self, request: Request, business_id: UUID, invoice_id: UUID) -> Response:
        """Get invoice by ID."""
        try:
            use_case = GetInvoiceUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_id=invoice_id,
            )
            invoice_dto = use_case.execute()

            # Check if invoice belongs to business
            if invoice_dto.business_id != business_id:
                return self.error(
                    message="Invoice not found for this business",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
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
