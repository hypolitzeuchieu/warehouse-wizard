from django.db import models
from authentication.models import User
from stock.models import Product

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('credit', 'Credit'),
    ]

    number = models.PositiveIntegerField(unique=True, editable=False)
    date = models.DateTimeField(auto_now_add=True)
    client_name = models.CharField(max_length=100, blank=True, null=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="invoices")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    due_date = models.DateField(blank=True, null=True)
    is_credit_settled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date']
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self):
        return f"Invoice {self.number} - {self.status}"

    def save(self, *args, **kwargs):
        # Génère automatiquement un numéro si non défini
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
        ('LOW_STOCK', 'Low Stock'),
        ('EXPIRED', 'Expired Product'),
        ('NEAR_EXPIRY', 'Near Expiry'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.type} for {self.product.name}"


class InventoryReport(models.Model):
    date = models.DateField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="inventory_reports"
    )
    total_products = models.PositiveIntegerField(default=0)
    expired_products = models.PositiveIntegerField(default=0)
    low_stock_products = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Inventory Report"
        verbose_name_plural = "Inventory Reports"

    def __str__(self):
        return f"Inventory Report - {self.date}"


class SalesReport(models.Model):
    date = models.DateField(auto_now_add=True)
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_invoices = models.PositiveIntegerField(default=0)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sales_reports"
    )

    class Meta:
        verbose_name = "Sales Report"
        verbose_name_plural = "Sales Reports"

    def __str__(self):
        return f"Sales Report - {self.date}"
