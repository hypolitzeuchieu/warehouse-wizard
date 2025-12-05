"""Report repository implementations."""

from datetime import datetime
from uuid import UUID

from django.db import connection

from domain.reports.entities import (
    Report,
    ReportFormat,
    ReportStatus,
    ReportType,
)
from domain.reports.repositories import ReportRepository
from infrastructure.persistence.models.report_models import Report as ReportModel


class ReportRepositoryImpl(ReportRepository):
    """Django implementation of ReportRepository."""

    def get_by_id(self, report_id: UUID, force_refresh: bool = False) -> Report | None:
        """
        Get report by ID.

        Args:
            report_id: Report ID
            force_refresh: If True, force a fresh read from database (bypass all caches)
        """
        try:
            if force_refresh:
                connection.close()
                connection.ensure_connection()
                model = ReportModel.objects.only(
                    "id",
                    "business_id",
                    "report_type",
                    "format",
                    "status",
                    "start_date",
                    "end_date",
                    "file_path",
                    "file_url",
                    "file_size",
                    "generated_by_id",
                    "error_message",
                    "metadata",
                    "created_at",
                    "updated_at",
                ).get(id=report_id)
                model.refresh_from_db()
            else:
                model = ReportModel.objects.get(id=report_id)

            return self._to_entity(model)
        except ReportModel.DoesNotExist:
            return None

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
        queryset = ReportModel.objects.filter(business_id=business_id)
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        if status:
            queryset = queryset.filter(status=status)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        queryset = queryset.order_by("-created_at")[:limit]
        return [self._to_entity(model) for model in queryset]

    def create(self, report: Report) -> Report:
        """Create a new report."""
        model = ReportModel(
            id=report.id,
            business_id=report.business_id,
            report_type=report.report_type.value,
            format=report.format.value,
            status=report.status.value,
            start_date=report.start_date,
            end_date=report.end_date,
            file_path=report.file_path,
            file_url=report.file_url,
            file_size=report.file_size,
            generated_by_id=report.generated_by,
            error_message=report.error_message,
            metadata=report.metadata,
        )
        model.save()
        return self._to_entity(model)

    def update(self, report: Report) -> Report:
        """
        Update an existing report.

        """
        rows_updated = ReportModel.objects.filter(id=report.id).update(
            report_type=report.report_type.value,
            format=report.format.value,
            status=report.status.value,
            start_date=report.start_date,
            end_date=report.end_date,
            file_path=report.file_path,
            file_url=report.file_url,
            file_size=report.file_size,
            generated_by_id=report.generated_by,
            error_message=report.error_message,
            metadata=report.metadata,
            updated_at=report.updated_at,
        )

        if rows_updated == 0:
            raise ValueError(f"Report {report.id} not found for update")
        connection.commit()

        connection.close()
        model = ReportModel.objects.only(
            "id",
            "business_id",
            "report_type",
            "format",
            "status",
            "start_date",
            "end_date",
            "file_path",
            "file_url",
            "file_size",
            "generated_by_id",
            "error_message",
            "metadata",
            "created_at",
            "updated_at",
        ).get(id=report.id)

        return self._to_entity(model)

    def delete(self, report_id: UUID) -> None:
        """Delete a report."""
        ReportModel.objects.filter(id=report_id).delete()

    def _to_entity(self, model: ReportModel) -> Report:
        """Convert model to entity."""
        return Report(
            id=model.id,
            business_id=model.business_id,
            report_type=ReportType(model.report_type),
            format=ReportFormat(model.format),
            status=ReportStatus(model.status),
            start_date=model.start_date,
            end_date=model.end_date,
            file_path=model.file_path,
            file_url=model.file_url,
            file_size=model.file_size,
            generated_by=model.generated_by_id if model.generated_by else None,
            error_message=model.error_message,
            metadata=model.metadata or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
