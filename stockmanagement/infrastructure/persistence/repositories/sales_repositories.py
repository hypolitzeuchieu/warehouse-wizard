"""Sales repository implementations."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import Count, Sum
from django.utils import timezone

from domain.sales.entities import (
    Invoice,
    InvoiceLine,
    InvoiceLog,
    InvoiceLogAction,
    InvoicePayment,
    InvoiceStatus,
    Order,
    OrderItem,
    PaymentMethod,
)
from domain.sales.repositories import (
    InvoiceLineRepository,
    InvoiceLogRepository,
    InvoicePaymentRepository,
    InvoiceRepository,
    OrderItemRepository,
    OrderRepository,
)
from infrastructure.persistence.models.sales_models import (
    Invoice as InvoiceModel,
)
from infrastructure.persistence.models.sales_models import (
    InvoiceLine as InvoiceLineModel,
)
from infrastructure.persistence.models.sales_models import (
    InvoiceLog as InvoiceLogModel,
)
from infrastructure.persistence.models.sales_models import (
    InvoicePayment as InvoicePaymentModel,
)
from infrastructure.persistence.models.sales_models import (
    Order as OrderModel,
)
from infrastructure.persistence.models.sales_models import (
    OrderItem as OrderItemModel,
)


class InvoiceRepositoryImpl(InvoiceRepository):
    """Django implementation of InvoiceRepository."""

    def get_by_id(self, invoice_id: UUID) -> Invoice | None:
        """Get invoice by ID."""
        try:
            invoice_model = InvoiceModel.objects.select_related(
                "business", "customer", "cashier"
            ).get(id=invoice_id)
            return self._to_entity(invoice_model)
        except InvoiceModel.DoesNotExist:
            return None

    def get_by_id_for_update(self, invoice_id: UUID) -> Invoice | None:
        """Get invoice by ID with row lock for update (prevents race conditions)."""
        try:
            invoice_model = (
                InvoiceModel.objects.select_related("business", "customer", "cashier")
                .select_for_update(of=(InvoiceModel,))
                .get(id=invoice_id)
            )
            return self._to_entity(invoice_model)
        except InvoiceModel.DoesNotExist:
            return None

    def get_by_number(self, business_id: UUID, number: int) -> Invoice | None:
        """Get invoice by number."""
        try:
            invoice_model = InvoiceModel.objects.select_related(
                "business", "customer", "cashier"
            ).get(business_id=business_id, number=number)
            return self._to_entity(invoice_model)
        except InvoiceModel.DoesNotExist:
            return None

    def get_by_business(
        self,
        business_id: UUID,
        status: InvoiceStatus | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        archived_only: bool = False,
    ) -> list[Invoice]:
        """Get invoices for a business with optional filters."""
        query = (
            InvoiceModel.objects.filter(business_id=business_id)
            .select_related("customer", "cashier")
            .prefetch_related(
                "lines__product__category",
                "lines__product__subcategory",
            )
        )

        if archived_only:
            query = query.filter(is_archived=True)
        else:
            query = query.filter(is_archived=False)

        if status:
            query = query.filter(status=status.value)

        if start_date:
            if timezone.is_naive(start_date):
                start_date = timezone.make_aware(start_date)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(created_at__gte=start_date)

        if end_date:
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(created_at__lte=end_date)

        invoices = query.order_by("-created_at")[:limit]
        return [self._to_entity(invoice) for invoice in invoices]

    def create(self, invoice: Invoice) -> Invoice:
        """Create a new invoice."""
        invoice_model = InvoiceModel(
            id=invoice.id,
            business_id=invoice.business_id,
            number=invoice.number,
            customer_name=invoice.customer_name,
            customer_id=invoice.customer_id,
            cashier_id=invoice.cashier_id,
            status=invoice.status.value,
            total=invoice.total,
            tax=invoice.tax,
            total_discount=invoice.total_discount,
            advance_paid=invoice.advance_paid,
            remaining_amount=invoice.remaining_amount,
            payment_method=invoice.payment_method.value,
            due_date=invoice.due_date,
            is_credit_settled=invoice.is_credit_settled,
            reason=invoice.reason,
            is_archived=invoice.is_archived,
        )
        invoice_model.save()
        return self._to_entity(invoice_model)

    def update(self, invoice: Invoice) -> Invoice:
        """Update an existing invoice."""
        invoice_model = InvoiceModel.objects.get(id=invoice.id)

        invoice_model.status = invoice.status.value
        invoice_model.total = invoice.total
        invoice_model.tax = invoice.tax
        invoice_model.total_discount = invoice.total_discount
        invoice_model.advance_paid = invoice.advance_paid
        invoice_model.remaining_amount = invoice.remaining_amount
        invoice_model.payment_method = invoice.payment_method.value
        invoice_model.due_date = invoice.due_date
        invoice_model.is_credit_settled = invoice.is_credit_settled
        invoice_model.reason = invoice.reason
        invoice_model.is_archived = invoice.is_archived
        invoice_model.save()
        return self._to_entity(invoice_model)

    def get_next_invoice_number(self, business_id: UUID) -> int:
        """Get next invoice number for a business."""
        last_invoice = (
            InvoiceModel.objects.filter(business_id=business_id).order_by("-number").first()
        )
        if last_invoice:
            return last_invoice.number + 1
        return 1

    def get_sales_aggregations_for_report(
        self,
        business_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Get optimized sales aggregations for reports using DB aggregations.

        This method uses database aggregations instead of Python loops
        to optimize performance for large datasets.

        Args:
            business_id: Business ID
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Dictionary with aggregated statistics
        """
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)

        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        total_stats = InvoiceModel.objects.filter(
            business_id=business_id,
            is_archived=False,
            created_at__gte=start_date,
            created_at__lte=end_date,
        ).aggregate(
            total_revenue=Sum("total"),
            total_invoices=Count("id"),
        )

        items_sold_stats = InvoiceLineModel.objects.filter(
            invoice__business_id=business_id,
            invoice__is_archived=False,
            invoice__created_at__gte=start_date,
            invoice__created_at__lte=end_date,
        ).aggregate(
            total_items_sold=Sum("quantity"),
        )

        payment_method_stats = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                is_archived=False,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )
            .values("payment_method")
            .annotate(
                total_amount=Sum("total"),
                invoice_count=Count("id"),
            )
            .order_by("-total_amount")
        )

        status_stats = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                is_archived=False,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )
            .values("status")
            .annotate(
                total_amount=Sum("total"),
                invoice_count=Count("id"),
            )
            .order_by("-total_amount")
        )

        product_stats = (
            InvoiceLineModel.objects.filter(
                invoice__business_id=business_id,
                invoice__is_archived=False,
                invoice__created_at__gte=start_date,
                invoice__created_at__lte=end_date,
            )
            .select_related("product")
            .values("product_id", "product__name")
            .annotate(
                total_quantity_sold=Sum("quantity"),
                total_revenue=Sum("line_total"),
                number_of_sales=Count("invoice_id", distinct=True),
            )
            .order_by("-total_revenue")[:10]
        )

        customer_stats = (
            InvoiceModel.objects.filter(
                business_id=business_id,
                is_archived=False,
                created_at__gte=start_date,
                created_at__lte=end_date,
                customer_id__isnull=False,
            )
            .values("customer_id", "customer_name")
            .annotate(
                total_purchases=Sum("total"),
                number_of_invoices=Count("id"),
            )
            .order_by("-total_purchases")[:10]
        )

        payment_method_stats_list = list(payment_method_stats)
        status_stats_list = list(status_stats)
        product_stats_list = list(product_stats)
        customer_stats_list = list(customer_stats)

        return {
            "total_revenue": Decimal(str(total_stats["total_revenue"] or 0)),
            "total_invoices": total_stats["total_invoices"] or 0,
            "total_items_sold": items_sold_stats["total_items_sold"] or 0,
            "payment_method_stats": payment_method_stats_list,
            "status_stats": status_stats_list,
            "product_stats": product_stats_list,
            "customer_stats": customer_stats_list,
        }

    def delete(self, invoice_id: UUID) -> None:
        """Permanently delete an invoice (hard delete)."""
        InvoiceModel.objects.filter(id=invoice_id).delete()

    def _to_entity(self, invoice_model: InvoiceModel) -> Invoice:
        """Convert Django model to domain entity."""
        return Invoice(
            id=invoice_model.id,
            business_id=invoice_model.business_id,
            number=invoice_model.number,
            customer_name=invoice_model.customer_name,
            customer_id=invoice_model.customer_id,
            cashier_id=invoice_model.cashier_id,
            status=InvoiceStatus(invoice_model.status),
            total=invoice_model.total,
            tax=invoice_model.tax,
            total_discount=invoice_model.total_discount,
            advance_paid=invoice_model.advance_paid,
            remaining_amount=invoice_model.remaining_amount,
            payment_method=PaymentMethod(invoice_model.payment_method),
            due_date=invoice_model.due_date,
            is_credit_settled=invoice_model.is_credit_settled,
            created_at=invoice_model.created_at,
            updated_at=invoice_model.updated_at,
            reason=invoice_model.reason,
            is_archived=invoice_model.is_archived,
        )


class InvoiceLineRepositoryImpl(InvoiceLineRepository):
    """Django implementation of InvoiceLineRepository."""

    def get_by_id(self, line_id: UUID) -> InvoiceLine | None:
        """Get invoice line by ID."""
        try:
            line_model = InvoiceLineModel.objects.select_related("invoice", "product").get(
                id=line_id
            )
            return self._to_entity(line_model)
        except InvoiceLineModel.DoesNotExist:
            return None

    def get_by_invoice(self, invoice_id: UUID) -> list[InvoiceLine]:
        """Get all lines for an invoice."""
        lines = InvoiceLineModel.objects.filter(invoice_id=invoice_id).select_related("product")
        return [self._to_entity(line) for line in lines]

    def create(self, line: InvoiceLine) -> InvoiceLine:
        """Create a new invoice line."""
        line_model = InvoiceLineModel(
            id=line.id,
            invoice_id=line.invoice_id,
            product_id=line.product_id,
            quantity=line.quantity,
            unit_price=line.unit_price,
            discount=line.discount,
            line_total=line.line_total,
        )
        line_model.save()
        return self._to_entity(line_model)

    def delete(self, line_id: UUID) -> None:
        """Delete an invoice line."""
        InvoiceLineModel.objects.filter(id=line_id).delete()

    def _to_entity(self, line_model: InvoiceLineModel) -> InvoiceLine:
        """Convert Django model to domain entity."""
        return InvoiceLine(
            id=line_model.id,
            invoice_id=line_model.invoice_id,
            product_id=line_model.product_id,
            quantity=line_model.quantity,
            unit_price=line_model.unit_price,
            discount=line_model.discount,
            line_total=line_model.line_total,
            created_at=line_model.created_at,
        )


class OrderRepositoryImpl(OrderRepository):
    """Django implementation of OrderRepository."""

    def get_by_id(self, order_id: UUID) -> Order | None:
        """Get order by ID."""
        try:
            order_model = OrderModel.objects.select_related("business", "customer").get(id=order_id)
            return self._to_entity(order_model)
        except OrderModel.DoesNotExist:
            return None

    def get_by_customer(self, customer_id: UUID, limit: int = 100) -> list[Order]:
        """Get orders for a customer."""
        orders = (
            OrderModel.objects.filter(customer_id=customer_id)
            .select_related("business")
            .order_by("-created_at")[:limit]
        )
        return [self._to_entity(order) for order in orders]

    def get_by_business(
        self,
        business_id: UUID,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders for a business."""
        query = OrderModel.objects.filter(business_id=business_id).select_related("customer")

        if status:
            query = query.filter(status=status)

        orders = query.order_by("-created_at")[:limit]
        return [self._to_entity(order) for order in orders]

    def create(self, order: Order) -> Order:
        """Create a new order."""
        order_model = OrderModel(
            id=order.id,
            business_id=order.business_id,
            customer_id=order.customer_id,
            order_number=order.order_number,
            status=order.status,
            total=order.total,
            payment_method=order.payment_method.value if order.payment_method else None,
            shipping_address=order.shipping_address,
            notes=order.notes,
            delivered_at=order.delivered_at,
        )
        order_model.save()
        return self._to_entity(order_model)

    def update(self, order: Order) -> Order:
        """Update an existing order."""
        order_model = OrderModel.objects.get(id=order.id)
        order_model.status = order.status
        order_model.total = order.total
        order_model.payment_method = order.payment_method.value if order.payment_method else None
        order_model.shipping_address = order.shipping_address
        order_model.notes = order.notes
        order_model.delivered_at = order.delivered_at
        order_model.save()
        return self._to_entity(order_model)

    def _to_entity(self, order_model: OrderModel) -> Order:
        """Convert Django model to domain entity."""
        return Order(
            id=order_model.id,
            business_id=order_model.business_id,
            customer_id=order_model.customer_id,
            order_number=order_model.order_number,
            status=order_model.status,
            total=order_model.total,
            payment_method=(
                PaymentMethod(order_model.payment_method) if order_model.payment_method else None
            ),
            shipping_address=order_model.shipping_address,
            notes=order_model.notes,
            created_at=order_model.created_at,
            updated_at=order_model.updated_at,
            delivered_at=order_model.delivered_at,
        )


class OrderItemRepositoryImpl(OrderItemRepository):
    """Django implementation of OrderItemRepository."""

    def get_by_order(self, order_id: UUID) -> list[OrderItem]:
        """Get all items for an order."""
        items = OrderItemModel.objects.filter(order_id=order_id).select_related("product")
        return [self._to_entity(item) for item in items]

    def create(self, item: OrderItem) -> OrderItem:
        """Create a new order item."""
        item_model = OrderItemModel(
            id=item.id,
            order_id=item.order_id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        item_model.save()
        return self._to_entity(item_model)

    def _to_entity(self, item_model: OrderItemModel) -> OrderItem:
        """Convert Django model to domain entity."""
        return OrderItem(
            id=item_model.id,
            order_id=item_model.order_id,
            product_id=item_model.product_id,
            quantity=item_model.quantity,
            unit_price=item_model.unit_price,
            line_total=item_model.line_total,
            created_at=item_model.created_at,
        )


class InvoicePaymentRepositoryImpl(InvoicePaymentRepository):
    """Django implementation of InvoicePaymentRepository."""

    def get_by_id(self, payment_id: UUID) -> InvoicePayment | None:
        """Get payment by ID."""
        try:
            payment_model = InvoicePaymentModel.objects.select_related("invoice", "created_by").get(
                id=payment_id
            )
            return self._to_entity(payment_model)
        except InvoicePaymentModel.DoesNotExist:
            return None

    def get_by_invoice(self, invoice_id: UUID, limit: int = 100) -> list[InvoicePayment]:
        """Get all payments for an invoice."""
        payments = (
            InvoicePaymentModel.objects.filter(invoice_id=invoice_id)
            .select_related("created_by")
            .order_by("-payment_date")[:limit]
        )
        return [self._to_entity(payment) for payment in payments]

    def get_by_idempotency_key(
        self, invoice_id: UUID, idempotency_key: UUID
    ) -> InvoicePayment | None:
        """Get payment by idempotency key for an invoice (prevents double-spending)."""
        try:
            payment_model = InvoicePaymentModel.objects.select_related("invoice", "created_by").get(
                invoice_id=invoice_id, idempotency_key=idempotency_key
            )
            return self._to_entity(payment_model)
        except InvoicePaymentModel.DoesNotExist:
            return None

    def get_by_business(
        self,
        business_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[InvoicePayment]:
        """Get all payments for a business (excluding payments from archived invoices)."""
        query = InvoicePaymentModel.objects.filter(
            invoice__business_id=business_id,
            invoice__is_archived=False,
        ).select_related("invoice", "created_by")

        if start_date:
            query = query.filter(payment_date__gte=start_date)

        if end_date:
            query = query.filter(payment_date__lte=end_date)

        payments = query.order_by("-payment_date")[:limit]
        return [self._to_entity(payment) for payment in payments]

    def create(self, payment: InvoicePayment) -> InvoicePayment:
        """Create a new payment."""
        payment_model = InvoicePaymentModel(
            id=payment.id,
            invoice_id=payment.invoice_id,
            amount=payment.amount,
            payment_method=payment.payment_method.value,
            change_amount=payment.change_amount,
            refund_amount=payment.refund_amount,
            payment_date=payment.payment_date,
            notes=payment.notes,
            idempotency_key=payment.idempotency_key,
            created_by_id=payment.created_by,
        )
        payment_model.save()
        return self._to_entity(payment_model)

    def _to_entity(self, payment_model: InvoicePaymentModel) -> InvoicePayment:
        """Convert Django model to domain entity."""
        return InvoicePayment(
            id=payment_model.id,
            invoice_id=payment_model.invoice_id,
            amount=payment_model.amount,
            payment_method=PaymentMethod(payment_model.payment_method),
            change_amount=payment_model.change_amount,
            refund_amount=payment_model.refund_amount,
            payment_date=payment_model.payment_date,
            notes=payment_model.notes,
            idempotency_key=payment_model.idempotency_key,
            created_at=payment_model.created_at,
            updated_at=payment_model.updated_at,
            created_by=payment_model.created_by_id,
        )


class InvoiceLogRepositoryImpl(InvoiceLogRepository):
    """Django implementation of InvoiceLogRepository."""

    def get_by_id(self, log_id: UUID) -> InvoiceLog | None:
        """Get log by ID."""
        try:
            log_model = InvoiceLogModel.objects.select_related("invoice", "created_by").get(
                id=log_id
            )
            return self._to_entity(log_model)
        except InvoiceLogModel.DoesNotExist:
            return None

    def get_by_invoice(self, invoice_id: UUID, limit: int = 100) -> list[InvoiceLog]:
        """Get all logs for an invoice."""
        logs = (
            InvoiceLogModel.objects.filter(invoice_id=invoice_id)
            .select_related("created_by")
            .order_by("-created_at")[:limit]
        )
        return [self._to_entity(log) for log in logs]

    def create(self, log: InvoiceLog) -> InvoiceLog:
        """Create a new log entry."""
        log_model = InvoiceLogModel(
            id=log.id,
            invoice_id=log.invoice_id,
            action=log.action.value,
            old_value=log.old_value,
            new_value=log.new_value,
            description=log.description,
            created_by_id=log.created_by,
        )
        log_model.save()
        return self._to_entity(log_model)

    def _to_entity(self, log_model: InvoiceLogModel) -> InvoiceLog:
        """Convert Django model to domain entity."""
        return InvoiceLog(
            id=log_model.id,
            invoice_id=log_model.invoice_id,
            action=InvoiceLogAction(log_model.action),
            old_value=log_model.old_value,
            new_value=log_model.new_value,
            description=log_model.description,
            created_at=log_model.created_at,
            updated_at=log_model.updated_at,
            created_by=log_model.created_by_id,
        )
