"""Sales repository implementations."""

from datetime import datetime
from uuid import UUID

from domain.sales.entities import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Order,
    OrderItem,
    PaymentMethod,
)
from domain.sales.repositories import (
    InvoiceLineRepository,
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
    ) -> list[Invoice]:
        """Get invoices for a business with optional filters."""
        query = InvoiceModel.objects.filter(business_id=business_id).select_related(
            "customer", "cashier"
        )

        if status:
            query = query.filter(status=status.value)

        if start_date:
            query = query.filter(created_at__gte=start_date)

        if end_date:
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
            discount=invoice.discount,
            advance_paid=invoice.advance_paid,
            remaining_amount=invoice.remaining_amount,
            payment_method=invoice.payment_method.value,
            due_date=invoice.due_date,
            is_credit_settled=invoice.is_credit_settled,
            reason=invoice.reason,
        )
        invoice_model.save()
        return self._to_entity(invoice_model)

    def update(self, invoice: Invoice) -> Invoice:
        """Update an existing invoice."""
        invoice_model = InvoiceModel.objects.get(id=invoice.id)
        invoice_model.status = invoice.status.value
        invoice_model.total = invoice.total
        invoice_model.tax = invoice.tax
        invoice_model.discount = invoice.discount
        invoice_model.advance_paid = invoice.advance_paid
        invoice_model.remaining_amount = invoice.remaining_amount
        invoice_model.payment_method = invoice.payment_method.value
        invoice_model.due_date = invoice.due_date
        invoice_model.is_credit_settled = invoice.is_credit_settled
        invoice_model.reason = invoice.reason
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
            discount=invoice_model.discount,
            advance_paid=invoice_model.advance_paid,
            remaining_amount=invoice_model.remaining_amount,
            payment_method=PaymentMethod(invoice_model.payment_method),
            due_date=invoice_model.due_date,
            is_credit_settled=invoice_model.is_credit_settled,
            created_at=invoice_model.created_at,
            updated_at=invoice_model.updated_at,
            reason=invoice_model.reason,
        )


class InvoiceLineRepositoryImpl(InvoiceLineRepository):
    """Django implementation of InvoiceLineRepository."""

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
