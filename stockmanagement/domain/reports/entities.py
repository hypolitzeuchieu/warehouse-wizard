"""Report domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class ReportType(str, Enum):
    """Report type enumeration."""

    SALES = "sales"
    INVENTORY = "inventory"
    STOCK = "stock"


class ReportFormat(str, Enum):
    """Report format enumeration."""

    HTML = "html"
    PDF = "pdf"


class ReportStatus(str, Enum):
    """Report status enumeration."""

    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Report:
    """Report entity."""

    id: UUID
    business_id: UUID
    report_type: ReportType
    format: ReportFormat
    status: ReportStatus
    start_date: datetime | None
    end_date: datetime | None
    file_path: str | None
    file_url: str | None
    file_size: int | None
    generated_by: UUID | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] | None = None
