"""Report DTOs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class ReportCreateDTO:
    """DTO for creating a report."""

    business_id: UUID
    report_type: str  # sales, inventory, stock
    format: str = "pdf"  # pdf
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass
class ReportResponseDTO:
    """DTO for report response."""

    id: UUID
    business_id: UUID
    report_type: str
    format: str
    status: str
    start_date: datetime | None
    end_date: datetime | None
    file_url: str | None
    file_size: int | None
    generated_by: UUID | None
    error_message: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
