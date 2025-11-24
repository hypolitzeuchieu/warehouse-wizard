"""Sales domain Django models."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.customer_models import Customer
from infrastructure.persistence.models.inventory_models import Product
from infrastructure.persistence.models.user_models import RetailPulseUser


class Invoice(BaseModel):
    """Invoice model."""

    STATUS_CHOICES = [
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
        ("CREDIT", "Credit"),
        ("PENDING", "Pending"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("mobile_money", "Mobile Money"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("credit", "Credit"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="invoices")
    number = models.PositiveIntegerField()
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    cashier = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="processed_invoices",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    total = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    tax = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    advance_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    remaining_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash")
    due_date = models.DateField(null=True, blank=True)
    is_credit_settled = models.BooleanField(default=False)
    reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "invoices"
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        unique_together = [["business", "number"]]
        indexes = [
            models.Index(fields=["business", "-updated_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["customer"]),
        ]

    def __str__(self) -> str:
        return f"Invoice {self.number} - {self.business.name}"

    def calculate_total(self) -> Decimal:
        """Calculate total amount."""
        return self.total + self.tax - self.discount

    def get_remaining_amount(self) -> Decimal:
        """Get remaining amount to be paid."""
        if self.status == "CREDIT":
            return max(self.total - self.advance_paid, Decimal("0.00"))
        return Decimal("0.00")


class InvoiceLine(BaseModel):
    """Invoice line item model."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="invoice_lines")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    discount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )

    class Meta:
        db_table = "invoice_lines"
        verbose_name = "Invoice Line"
        verbose_name_plural = "Invoice Lines"
        indexes = [
            models.Index(fields=["invoice"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} (x{self.quantity})"

    def save(self, *args, **kwargs):
        """Calculate line total before saving."""
        self.line_total = (self.unit_price * self.quantity) - self.discount
        super().save(*args, **kwargs)


class Order(BaseModel):
    """Order model for customer orders."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("mobile_money", "Mobile Money"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="orders")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    order_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True
    )
    shipping_address = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders"
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=["business", "-updated_at"]),
            models.Index(fields=["customer", "-updated_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["order_number"]),
        ]

    def __str__(self) -> str:
        return f"Order {self.order_number} - {self.customer.name}"


class OrderItem(BaseModel):
    """Order item model."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="order_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    line_total = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )

    class Meta:
        db_table = "order_items"
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        indexes = [
            models.Index(fields=["order"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} (x{self.quantity})"

    def save(self, *args, **kwargs):
        """Calculate line total before saving."""
        self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class InvoicePayment(BaseModel):
    """Invoice payment model to track all payments made on an invoice."""

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("mobile_money", "Mobile Money"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("credit", "Credit"),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash")
    change_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Amount returned to customer (overpayment)",
    )
    refund_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Amount refunded to customer",
    )
    payment_date = models.DateTimeField()
    notes = models.TextField(null=True, blank=True)
    idempotency_key = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        help_text="Prevents double-spending if payment is retried",
    )
    created_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_invoice_payments",
    )

    class Meta:
        db_table = "invoice_payments"
        verbose_name = "Invoice Payment"
        verbose_name_plural = "Invoice Payments"
        indexes = [
            models.Index(fields=["invoice", "-payment_date"]),
            models.Index(fields=["payment_date"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self) -> str:
        return f"Payment {self.amount} for Invoice {self.invoice.number}"


class InvoiceLog(BaseModel):
    """Invoice log model to track all actions on invoices."""

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("PAYMENT_RECEIVED", "Payment Received"),
        ("REFUNDED", "Refunded"),
        ("CANCELLED", "Cancelled"),
        ("LINE_ADDED", "Line Added"),
        ("LINE_REMOVED", "Line Removed"),
        ("LINE_UPDATED", "Line Updated"),
        ("CREDIT_APPLIED", "Credit Applied"),
        ("STATUS_CHANGED", "Status Changed"),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_invoice_logs",
    )

    class Meta:
        db_table = "invoice_logs"
        verbose_name = "Invoice Log"
        verbose_name_plural = "Invoice Logs"
        indexes = [
            models.Index(fields=["invoice", "-created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        return f"Log {self.action} for Invoice {self.invoice.number}"
