"""Sales ViewSet for invoices and orders."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

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
from presentation.serializers.sales_serializers import InvoiceCreateSerializer
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
            from shared.security.query_params_validator import QueryParamsValidator

            # Get and validate query parameters
            status_filter = QueryParamsValidator.validate_enum(
                request.query_params.get("status"),
                allowed_values=["PENDING", "PAID", "PARTIAL", "CANCELLED", "REFUNDED"],
                param_name="status",
            )
            start_date = QueryParamsValidator.validate_date(
                request.query_params.get("start_date"), param_name="start_date"
            )
            end_date = QueryParamsValidator.validate_date(
                request.query_params.get("end_date"), param_name="end_date"
            )
            limit = QueryParamsValidator.validate_limit(
                request.query_params.get("limit"), default=100
            )

            use_case = ListInvoicesUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                status=status_filter,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            invoices = use_case.execute()

            data = [
                {
                    "id": str(inv.id),
                    "business_id": str(inv.business_id),
                    "number": inv.number,
                    "customer_name": inv.customer_name,
                    "customer_id": str(inv.customer_id) if inv.customer_id else None,
                    "cashier_id": str(inv.cashier_id),
                    "status": inv.status,
                    "total": str(inv.total),
                    "tax": str(inv.tax),
                    "discount": str(inv.discount),
                    "advance_paid": str(inv.advance_paid),
                    "remaining_amount": str(inv.remaining_amount),
                    "payment_method": inv.payment_method,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                    "is_credit_settled": inv.is_credit_settled,
                    "reason": inv.reason,
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
                        for line in (inv.lines or [])
                    ],
                    "created_at": inv.created_at.isoformat(),
                    "updated_at": inv.updated_at.isoformat(),
                }
                for inv in invoices
            ]

            return self.success(
                message="Invoices retrieved successfully",
                data=data,
                status_code=status.HTTP_200_OK,
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
