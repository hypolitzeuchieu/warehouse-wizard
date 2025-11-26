"""Report repository interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from domain.reports.entities import Report


class ReportRepository(ABC):
    """Report repository interface."""

    @abstractmethod
    def get_by_id(self, report_id: UUID) -> Report | None:
        """Get report by ID."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        report_type: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[Report]:
        """Get reports for a business."""
        pass

    @abstractmethod
    def create(self, report: Report) -> Report:
        """Create a new report."""
        pass

    @abstractmethod
    def update(self, report: Report) -> Report:
        """Update an existing report."""
        pass

    @abstractmethod
    def delete(self, report_id: UUID) -> None:
        """Delete a report."""
        pass
