"""Report domain Django models."""

from __future__ import annotations

from django.db import models

from infrastructure.persistence.models.base_model import BaseModel
from infrastructure.persistence.models.business_models import Business
from infrastructure.persistence.models.user_models import RetailPulseUser


class Report(BaseModel):
    """Report model for storing generated reports."""

    REPORT_TYPE_CHOICES = [
        ("sales", "Sales Report"),
        ("inventory", "Inventory Report"),
        ("stock", "Stock Report"),
    ]

    FORMAT_CHOICES = [
        ("html", "HTML"),
        ("pdf", "PDF"),
    ]

    STATUS_CHOICES = [
        ("generating", "Generating"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="reports")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="html")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="generating")
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_url = models.URLField(max_length=1000, null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    generated_by = models.ForeignKey(
        RetailPulseUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="generated_reports",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "reports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "report_type", "status"]),
            models.Index(fields=["business", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.report_type} report for {self.business.name} ({self.id})"
