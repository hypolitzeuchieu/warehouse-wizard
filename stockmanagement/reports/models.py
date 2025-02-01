from decimal import Decimal

from django.db import models
from django.utils import timezone

from authentication.models import User
from stock.models import Product


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
        ("CREDIT", "Credit"),
    ]

    number = models.PositiveIntegerField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    client_name = models.CharField(max_length=100, blank=True, null=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="invoices")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    reason = models.TextField(blank=True, null=True)
    advance_paid = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    _remaining_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    due_date = models.DateField(blank=True, null=True)
    is_credit_settled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self):
        return f"Invoice {self.number} - {self.status}"

    @property
    def remaining_amount(self):
        if self.status == "CREDIT":
            return max(self.total - self.advance_paid, Decimal('0.00'))
        return Decimal('0.00')

    @remaining_amount.setter
    def remaining_amount(self, value):
        self._remaining_amount = value

    def save(self, *args, **kwargs):
        # automatically generate number if not define
        if not self.number:
            last_invoice = Invoice.objects.order_by('id').last()
            self.number = last_invoice.number + 1 if last_invoice else 1
        super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="invoice_lines"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Invoice Line"
        verbose_name_plural = "Invoice Lines"

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"

    def save(self, *args, **kwargs):
        # Calcul automatique du total de la ligne
        self.line_total = (self.unit_price * self.quantity) - self.discount
        super().save(*args, **kwargs)


class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        ('inventory', 'Inventory'),
        ('sales', 'Sales'),
        ('returns', 'Returns'),
        ('expired', 'Expired Products'),
    ]

    type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="reports")
    file_path = models.FileField(upload_to='reports/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Report"
        verbose_name_plural = "Reports"

    def __str__(self):
        return f"{self.type.capitalize()} Report - {self.generated_at.date()}"


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('CRITICAL_STOCK', 'Critical Stock'),
        ('EXPIRED', 'Expired Product'),
        ('NEAR_EXPIRY', 'Near Expiry'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default='CRITICAL_STOCK')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.type} for {self.product.name}"


class InventoryReport(models.Model):
    created_at = models.DateField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="inventory_reports"
    )
    total_products = models.PositiveIntegerField(default=0)
    expired_products = models.PositiveIntegerField(default=0)
    low_stock_products = models.PositiveIntegerField(default=0)
    date_range = models.CharField(max_length=255, default=None)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inventory Report"
        verbose_name_plural = "Inventory Reports"

    def __str__(self):
        return f"Inventory Report - {self.created_at}"


class SalesReport(models.Model):
    date = models.DateField(default=timezone.now, unique=True)
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_invoices = models.PositiveIntegerField(default=0)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sales_reports"
    )

    class Meta:
        ordering = ['-date']
        verbose_name = "Sales Report"
        verbose_name_plural = "Sales Reports"

    def __str__(self):
        return f"Sales Report - {self.date}"
