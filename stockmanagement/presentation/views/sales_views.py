"""Sales API views."""

from uuid import UUID

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.sales_use_cases import (
    CreateInvoiceUseCase,
    GetInvoiceUseCase,
)
from domain.inventory.services import InventoryDomainService
from infrastructure.persistence.repositories import (
    InvoiceLineRepositoryImpl,
    InvoiceRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
)
from presentation.serializers.sales_serializers import InvoiceCreateSerializer
from shared.response.mixin import ResponseMixin


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_invoice_view(request: Request, business_id: UUID) -> Response:
    """Create invoice endpoint (POS)."""
    serializer = InvoiceCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return ResponseMixin.error(
            message="Validation error",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
        )

    try:
        dto = serializer.to_dto()
        inventory_domain_service = InventoryDomainService(
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
        )
        use_case = CreateInvoiceUseCase(
            invoice_repository=InvoiceRepositoryImpl(),
            invoice_line_repository=InvoiceLineRepositoryImpl(),
            product_repository=ProductRepositoryImpl(),
            inventory_domain_service=inventory_domain_service,
            business_id=business_id,
            cashier_id=request.user.id,
        )
        invoice_dto = use_case.execute(dto)

        return ResponseMixin.success(
            message="Invoice created successfully",
            data={
                "id": str(invoice_dto.id),
                "business_id": str(invoice_dto.business_id),
                "number": invoice_dto.number,
                "customer_name": invoice_dto.customer_name,
                "customer_id": str(invoice_dto.customer_id) if invoice_dto.customer_id else None,
                "cashier_id": str(invoice_dto.cashier_id),
                "status": invoice_dto.status,
                "total": str(invoice_dto.total),
                "tax": str(invoice_dto.tax),
                "discount": str(invoice_dto.discount),
                "remaining_amount": str(invoice_dto.remaining_amount),
                "payment_method": invoice_dto.payment_method,
                "lines": [
                    {
                        "id": str(line.id),
                        "product_id": str(line.product_id),
                        "product_name": line.product_name,
                        "quantity": line.quantity,
                        "unit_price": str(line.unit_price),
                        "discount": str(line.discount),
                        "line_total": str(line.line_total),
                    }
                    for line in invoice_dto.lines or []
                ],
                "created_at": invoice_dto.created_at.isoformat(),
            },
            status_code=status.HTTP_201_CREATED,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_invoice_view(request: Request, business_id: UUID, invoice_id: UUID) -> Response:
    """Get invoice endpoint."""
    try:
        use_case = GetInvoiceUseCase(
            invoice_repository=InvoiceRepositoryImpl(),
            invoice_line_repository=InvoiceLineRepositoryImpl(),
            invoice_id=invoice_id,
        )
        invoice_dto = use_case.execute()

        return ResponseMixin.success(
            message="Invoice retrieved successfully",
            data={
                "id": str(invoice_dto.id),
                "business_id": str(invoice_dto.business_id),
                "number": invoice_dto.number,
                "customer_name": invoice_dto.customer_name,
                "customer_id": str(invoice_dto.customer_id) if invoice_dto.customer_id else None,
                "cashier_id": str(invoice_dto.cashier_id),
                "status": invoice_dto.status,
                "total": str(invoice_dto.total),
                "tax": str(invoice_dto.tax),
                "discount": str(invoice_dto.discount),
                "remaining_amount": str(invoice_dto.remaining_amount),
                "payment_method": invoice_dto.payment_method,
                "lines": [
                    {
                        "id": str(line.id),
                        "product_id": str(line.product_id),
                        "product_name": line.product_name,
                        "quantity": line.quantity,
                        "unit_price": str(line.unit_price),
                        "discount": str(line.discount),
                        "line_total": str(line.line_total),
                    }
                    for line in invoice_dto.lines or []
                ],
                "created_at": invoice_dto.created_at.isoformat(),
                "updated_at": invoice_dto.updated_at.isoformat(),
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ResponseMixin.from_exception(e)
