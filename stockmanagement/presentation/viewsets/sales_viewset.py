"""Sales ViewSet for invoices and orders."""

from __future__ import annotations

import json
from uuid import UUID

from django.http import HttpResponse
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
    ArchiveInvoiceUseCase,
    CancelInvoiceUseCase,
    CreateInvoiceUseCase,
    DeleteInvoiceUseCase,
    GenerateInvoiceReceiptUseCase,
    GetInvoiceUseCase,
    ListInvoicesUseCase,
    ListPaymentsUseCase,
    PayInvoiceUseCase,
    ProcessRefundUseCase,
    ScanBarcodeForSaleUseCase,
    SearchProductsForSaleUseCase,
    UpdateInvoiceUseCase,
)
from domain.business.services import BusinessDomainService
from domain.inventory.services import InventoryDomainService
from domain.notifications.services import NotificationDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CreditRepositoryImpl,
    CustomerRepositoryImpl,
    InvoiceLineRepositoryImpl,
    InvoiceLogRepositoryImpl,
    InvoicePaymentRepositoryImpl,
    InvoiceRepositoryImpl,
    NotificationRepositoryImpl,
    ProductRepositoryImpl,
    StockMovementRepositoryImpl,
    UserRepositoryImpl,
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
    PaymentListQuerySerializer,
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

    def _get_notification_domain_service(self) -> NotificationDomainService:
        """Get notification domain service instance."""
        return NotificationDomainService(
            notification_repository=NotificationRepositoryImpl(),
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    def _user_is_owner_or_manager(self, business_id: UUID, user_id: UUID) -> bool:
        """Check if the user is the business owner or a manager."""
        domain_service = self._get_business_domain_service()
        business = domain_service.get_business(business_id)
        if not business:
            return False
        if business.owner_id == user_id:
            return True
        return domain_service.is_user_manager(business_id, user_id)

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
                        "choices": ["PAID", "PARTIAL", "CANCELLED", "REFUNDED"],
                    },
                    "start_date": {"type": "datetime"},
                    "end_date": {"type": "datetime"},
                },
                additional_allowed_params=["business_id"],
            )
            filter_payload["filters"]["business_id"] = business_id
            filter_dto = InvoiceListFilterDTO.from_payload(filter_payload)

            use_case = ListInvoicesUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                status=filter_dto.status,
                start_date=filter_dto.start_date,
                end_date=filter_dto.end_date,
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
                archived_only=filter_dto.archived_only,
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
        operation_summary="List archived invoices",
        operation_description="List archived invoices for a business (owner/manager only).",
        query_serializer=InvoiceListQuerySerializer,
        responses={
            200: InvoiceResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Sales"],
    )
    @action(detail=False, methods=["get"], url_path="archives")
    def list_archived_invoices(self, request: Request) -> Response:
        """List archived invoices (restricted to owner/manager)."""
        try:
            query_serializer = InvoiceListQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]
            if not self._user_is_owner_or_manager(business_id, request.user.id):
                return self.error(
                    message="Only owners or managers can access archived invoices",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            filter_payload = self.parse_list_filters(
                request,
                search_fields=["customer_name", "cashier_name", "number"],
                order_fields=["created_at", "updated_at", "total", "number"],
                filter_definitions={
                    "status": {
                        "type": "enum",
                        "choices": ["PAID", "PARTIAL", "CANCELLED", "REFUNDED"],
                    },
                    "start_date": {"type": "datetime"},
                    "end_date": {"type": "datetime"},
                },
                additional_allowed_params=["business_id"],
            )
            filter_payload["filters"]["business_id"] = business_id
            filter_payload["filters"]["archived_only"] = True
            filter_dto = InvoiceListFilterDTO.from_payload(filter_payload)

            use_case = ListInvoicesUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                status=filter_dto.status,
                start_date=filter_dto.start_date,
                end_date=filter_dto.end_date,
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
                archived_only=filter_dto.archived_only,
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
                message="Archived invoices retrieved successfully",
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
                user_repository=UserRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                credit_repository=CreditRepositoryImpl(),
                customer_repository=CustomerRepositoryImpl(),
                notification_domain_service=self._get_notification_domain_service(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                cashier_id=request.user.id,
            )
            invoice_dto = use_case.execute(dto)

            return self.success(
                message="Invoice created successfully",
                data=InvoiceResponseSerializer.from_dto(invoice_dto),
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
                invoice_payment_repository=InvoicePaymentRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
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

            if invoice_dto.is_archived and not self._user_is_owner_or_manager(
                invoice_dto.business_id, request.user.id
            ):
                return self.error(
                    message="Only owners or managers can access archived invoices",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            return self.success(
                message="Invoice retrieved successfully",
                data=InvoiceResponseSerializer.from_dto(invoice_dto),
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
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                business_domain_service=self._get_business_domain_service(),
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
        operation_summary="Archive invoice",
        operation_description="Archive an invoice instead of deleting it. Archived invoices remain read-only and require owner/manager access.",
        responses={
            200: "Invoice archived successfully",
            400: "Validation error",
            403: "Permission denied",
            404: "Invoice not found",
            500: "Internal server error",
            401: "Authentication credentials were not provided.",
        },
        tags=["Sales"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Archive (soft-delete) an invoice."""
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

            if not self._user_is_owner_or_manager(invoice.business_id, request.user.id):
                return self.error(
                    message="Only owners or managers can archive invoices",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
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

            use_case = ArchiveInvoiceUseCase(
                invoice_repository=invoice_repo,
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            use_case.execute(reason=reason)

            return self.success(
                message="Invoice archived successfully",
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
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                inventory_domain_service=self._get_inventory_domain_service(),
                credit_repository=CreditRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
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
        operation_summary="Permanently delete invoice",
        operation_description="Permanently delete an invoice from the database. This action cannot be undone. Only owners and managers can perform this action.",
        responses={
            204: "Invoice deleted successfully",
            400: "Bad Request",
            403: "Permission denied (owner/manager only)",
            404: "Invoice not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path="delete",
    )
    def delete_invoice(self, request: Request, pk: UUID) -> Response:
        """Permanently delete an invoice (hard delete)."""
        try:
            use_case = DeleteInvoiceUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                credit_repository=CreditRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Invoice deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT,
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
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                credit_repository=CreditRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
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
        operation_summary="List payments",
        operation_description="List payments for a business (owner/manager only).",
        query_serializer=PaymentListQuerySerializer,
        responses={
            200: PaymentResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Sales"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="payments/history",
    )
    def list_payments(self, request: Request) -> Response:
        """List payments for a business."""
        serializer = PaymentListQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        business_id = serializer.validated_data["business_id"]
        if not self._user_is_owner_or_manager(business_id, request.user.id):
            return self.error(
                message="Only owners or managers can view payments",
                status_code=status.HTTP_403_FORBIDDEN,
                code="PERMISSION_DENIED",
            )

        try:
            user_repo = UserRepositoryImpl()
            use_case = ListPaymentsUseCase(
                invoice_payment_repository=InvoicePaymentRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                start_date=serializer.validated_data.get("start_date"),
                end_date=serializer.validated_data.get("end_date"),
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
                user_repository=user_repo,
            )
            payments = use_case.execute()

            return self.paginated_response(
                request=request,
                queryset=payments,
                serializer_class=PaymentResponseSerializer,
                message="Payments retrieved successfully",
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
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
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
            user_repo = UserRepositoryImpl()
            payment_dtos = []
            for payment in payments:
                created_by_name: str | None = None
                if payment.created_by:
                    creator = user_repo.get_by_id(payment.created_by)
                    if creator:
                        created_by_name = creator.name or creator.email

                payment_dtos.append(
                    PaymentResponseDTO(
                        id=payment.id,
                        invoice_id=payment.invoice_id,
                        amount=payment.amount,
                        payment_method=payment.payment_method.value,
                        change_amount=payment.change_amount,
                        refund_amount=payment.refund_amount,
                        payment_date=payment.payment_date,
                        notes=payment.notes,
                        created_at=payment.created_at,
                        updated_at=payment.updated_at,
                        created_by=payment.created_by,
                        created_by_name=created_by_name,
                    )
                )

            return self.success(
                message="Payments retrieved successfully",
                data=[PaymentResponseSerializer.from_dto(p) for p in payment_dtos],
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Apply credit payment to invoice to pay the remaining amount",
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
        """Apply a credit payment to an invoice."""
        serializer = CreditApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = ApplyCreditToInvoiceUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                invoice_log_repository=InvoiceLogRepositoryImpl(),
                invoice_payment_repository=InvoicePaymentRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                credit_repository=CreditRepositoryImpl(),
                invoice_id=pk,
                user_id=request.user.id,
            )
            invoice_dto = use_case.execute(dto)

            return self.success(
                message="Credit payment applied successfully",
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

            query = serializer.validated_data.get("query", "")
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

    @swagger_auto_schema(
        operation_summary="Generate invoice receipt",
        operation_description="Generate a receipt for an invoice in small format with QR code. business_id is retrieved from the invoice.",
        manual_parameters=[
            openapi.Parameter(
                "output_format",
                openapi.IN_QUERY,
                description="Receipt format (pdf or html).",
                type=openapi.TYPE_STRING,
                enum=["pdf", "html"],
                required=False,
                default="pdf",
            ),
        ],
        responses={
            200: openapi.Response(
                "Receipt generated successfully (PDF)",
                schema=openapi.Schema(type=openapi.TYPE_FILE),
            ),
            400: "Bad Request",
            403: "Permission denied",
            404: "Invoice not found",
        },
        tags=["Sales"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="receipt",
    )
    def generate_receipt(self, request: Request, pk: UUID) -> Response:
        """Generate invoice receipt."""
        try:
            # Get invoice first to retrieve business_id
            invoice_repo = InvoiceRepositoryImpl()
            invoice = invoice_repo.get_by_id(pk)
            if not invoice:
                return self.error(
                    message="Invoice not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="INVOICE_NOT_FOUND",
                )

            format_param = request.query_params.get("output_format", "pdf").lower()
            if format_param not in ["pdf", "html"]:
                return self.error(
                    message="Invalid output_format. Must be 'pdf' or 'html'",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_FORMAT",
                )

            use_case = GenerateInvoiceReceiptUseCase(
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                business_repository=BusinessRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                user_repository=UserRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                invoice_id=pk,
                business_id=invoice.business_id,
                user_id=request.user.id,
                format=format_param,
            )
            receipt_dto = use_case.execute()

            # Return PDF
            if format_param == "pdf" and receipt_dto.receipt_pdf:
                response = HttpResponse(
                    receipt_dto.receipt_pdf,
                    content_type="application/pdf",
                )
                response["Content-Disposition"] = (
                    f'attachment; filename="receipt_{receipt_dto.invoice_number}.pdf"'
                )
                return response
            elif format_param == "html" and receipt_dto.receipt_html:
                return HttpResponse(
                    receipt_dto.receipt_html,
                    content_type="text/html",
                )
            else:
                return self.error(
                    message="Receipt not generated",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="RECEIPT_NOT_GENERATED",
                )
        except Exception as e:
            return self.handle_exception(e)
