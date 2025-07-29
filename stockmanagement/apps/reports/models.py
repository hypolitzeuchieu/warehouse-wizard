from __future__ import annotations

import uuid
from decimal import Decimal

from apps.authentication.models import User
from apps.stock.models import Product
from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('CREDIT', 'Credit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.PositiveIntegerField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    client_name = models.CharField(max_length=100, blank=True, null=True)
    cashier = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='invoices'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    total = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    tax = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    reason = models.TextField(blank=True, null=True)
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=3, default=0.00
    )
    advance_paid = models.DecimalField(
        max_digits=15, decimal_places=3, default=0.00
    )
    _remaining_amount = models.DecimalField(
        max_digits=10, decimal_places=3, default=0.00
    )
    due_date = models.DateField(blank=True, null=True)
    is_credit_settled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return f"Invoice {self.number} - {self.status}"

    @property
    def remaining_amount(self):
        if self.status == 'CREDIT':
            return max(self.total - self.advance_paid, Decimal('0.00'))
        return Decimal('0.00')

    @remaining_amount.setter
    def remaining_amount(self, value):
        self._remaining_amount = value

    def save(self, *args, **kwargs):
        if not self.number:
            last_invoice = Invoice.objects.order_by('-created_at').first()
            self.number = last_invoice.number + 1 if last_invoice else 1
        super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='lines'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='invoice_lines'
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=3)
    discount = models.DecimalField(
        max_digits=10, decimal_places=3, default=0.00
    )
    line_total = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        verbose_name = 'Invoice Line'
        verbose_name_plural = 'Invoice Lines'

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='reports'
    )
    file_path = models.FileField(upload_to='reports/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'

    def __str__(self):
        return f"{self.type.capitalize()} Report - {self.generated_at.date()}"


class InventoryReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.OneToOneField(
        Report,
        on_delete=models.CASCADE,
        related_name='inventory_report',
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventory_reports',
    )
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(null=True, blank=True)
    total_products = models.PositiveIntegerField(default=0)
    expired_products = models.PositiveIntegerField(default=0)
    low_stock_products = models.PositiveIntegerField(default=0)
    stocks = models.ManyToManyField('stock.Stock')
    notes = models.TextField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inventory Report'
        verbose_name_plural = 'Inventory Reports'

    def __str__(self):
        return f"Inventory Report - {self.start_date.date()} to {self.end_date.date()}"


class SalesReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.OneToOneField(
        Report,
        on_delete=models.CASCADE,
        related_name='sales_report',
        null=True
    )
    date = models.DateField(default=timezone.now)
    total_sales = models.DecimalField(
        max_digits=15, decimal_places=3, default=0.00
    )
    total_invoices = models.PositiveIntegerField(default=0)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sales_reports',
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Sales Report'
        verbose_name_plural = 'Sales Reports'

    def __str__(self):
        return f"Sales Report - {self.date}"


class InvoiceArchive(models.Model):
    STATUS_CHOICES = [
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('CREDIT', 'Credit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.PositiveIntegerField()
    invoice_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    client_name = models.CharField(max_length=100, blank=True, null=True)
    cashier = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='archived_invoices'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    total = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    tax = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    reason = models.TextField(blank=True, null=True)
    refund_amount = models.DecimalField(
        max_digits=15, decimal_places=3, default=0.00
    )
    advance_paid = models.DecimalField(
        max_digits=15, decimal_places=3, default=0.00
    )
    _remaining_amount = models.DecimalField(
        max_digits=15, decimal_places=3, default=0.00
    )
    due_date = models.DateField(blank=True, null=True)
    is_credit_settled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Archived Invoice'
        verbose_name_plural = 'Archived Invoices'

    def __str__(self):
        return f"Invoice {self.number} - {self.status}"

    @property
    def remaining_amount(self):
        if self.status == 'CREDIT':
            return max(self.total - self.advance_paid, Decimal('0.00'))
        return Decimal('0.00')

    @remaining_amount.setter
    def remaining_amount(self, value):
        self._remaining_amount = value


class InvoiceArchiveLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        InvoiceArchive, on_delete=models.CASCADE, related_name='lines'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='archived_invoice_lines'
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    line_total = models.DecimalField(max_digits=15, decimal_places=3)

    class Meta:
        verbose_name = 'Archived Invoice Line'
        verbose_name_plural = 'Archived Invoice Lines'

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"


class Expense(models.Model):
    EXPENSE_TYPES = [
        ('REPLENISHMENT', 'Replenishment'),
        ('MISCELLANEOUS', 'Miscellaneous'),
        ('ELECTRICITY', 'Electricity Bill'),
        ('WATER', 'Water Bill'),
        ('SALARY', 'Salary'),
        ('EXTRA', 'Extra'),
        ('MAINTENANCE', 'Maintenance'),
        ('TAX', 'Tax'),
        ('RENT', 'Rent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPES)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='expenses'
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_expenses'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'

    def __str__(self):
        return f"{self.expense_type} - {self.amount}"


class Treasure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    balance = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    total_sales = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    total_expenses = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    total_credit = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    outstanding_debt = models.DecimalField(max_digits=15, decimal_places=3, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)
    history = models.JSONField(default=list)

    class Meta:
        verbose_name = 'Treasure'
        verbose_name_plural = 'Treasures'

    def __str__(self):
        return f"Treasure - Balance: {self.balance} (Fcfa)"
