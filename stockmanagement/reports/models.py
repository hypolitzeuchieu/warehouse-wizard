from django.db import models
from authentication.models import User
from stock.models import Product

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('credit', 'Credit'),
    ]

    number = models.PositiveIntegerField(unique=True)
    date = models.DateTimeField(auto_now_add=True)
    client_name = models.CharField(max_length=100, blank=True, null=True)
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="invoices")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    due_date = models.DateField(blank=True, null=True)
    is_credit_settled = models.BooleanField(default=False)

    def __str__(self):
        return f"Invoice {self.number} - {self.status}"

    @property
    def remaining_amount(self):
        return self.total - self.paid_amount

class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="invoice_lines"
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"


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

    def __str__(self):
        return f"{self.type.capitalize()} Report - {self.generated_at.date()}"


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('LOW_STOCK', 'Low Stock'),
        ('EXPIRED', 'Expired Product'),
        ('NEAR_EXPIRY', 'Near Expiry'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.type} for {self.product.name}"
