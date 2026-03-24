"""Celery tasks for report generation."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from celery import shared_task
from django.db import connection
from django.utils import timezone

from application.dto.report_dto import ReportCreateDTO
from domain.business.services import BusinessDomainService
from domain.reports.entities import ReportStatus
from domain.reports.repositories import ReportRepository
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    InvoiceLineRepositoryImpl,
    InvoiceRepositoryImpl,
    ProductRepositoryImpl,
    ReportRepositoryImpl,
    StockMovementRepositoryImpl,
    UserRepositoryImpl,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=270,
)
def generate_report_task(
    self,
    report_id: UUID,
    business_id: UUID,
    user_id: UUID,
    report_type: str,
    format: str,
    start_date: str | None,
    end_date: str | None,
) -> dict:
    """
    Generate report asynchronously in background.

    Args:
        report_id: ID of the report to generate
        business_id: Business ID
        user_id: User ID who requested the report
        report_type: Type of report (sales, inventory, stock)
        format: Format (html, pdf)
        start_date: Start date ISO string
        end_date: End date ISO string

    Returns:
        Dictionary with generation status
    """
    task_id = str(self.request.id)
    report_repository: ReportRepository = ReportRepositoryImpl()

    try:
        connection.close()

        report = report_repository.get_by_id(report_id)
        if not report:
            logger.error(
                f"Report {report_id} not found, task_id: {task_id}",
                extra={"report_id": str(report_id), "task_id": task_id},
            )
            return {"status": "failed", "error": "Report not found", "task_id": task_id}

        if report.status != ReportStatus.GENERATING:
            logger.warning(
                f"Report {report_id} is not in GENERATING status: {report.status.value}, "
                f"task_id: {task_id}",
                extra={
                    "report_id": str(report_id),
                    "task_id": task_id,
                    "current_status": report.status.value,
                },
            )
            return {"status": "skipped", "current_status": report.status.value, "task_id": task_id}

        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt)
            except (ValueError, TypeError) as e:
                logger.error(
                    "Invalid start_date format in task: %s (type: %s), error: %s",
                    start_date,
                    type(start_date).__name__,
                    str(e),
                    extra={"report_id": str(report_id), "task_id": task_id},
                )
                raise ValueError(f"Invalid start_date format: {start_date}") from e
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                if timezone.is_naive(end_dt):
                    end_dt = timezone.make_aware(end_dt)
            except (ValueError, TypeError) as e:
                logger.error(
                    "Invalid end_date format in task: %s (type: %s), error: %s",
                    end_date,
                    type(end_date).__name__,
                    str(e),
                    extra={"report_id": str(report_id), "task_id": task_id},
                )
                raise ValueError(f"Invalid end_date format: {end_date}") from e

        report_dto = ReportCreateDTO(
            business_id=business_id,
            report_type=report_type,
            format=format,
            start_date=start_dt,
            end_date=end_dt,
        )

        business_domain_service = BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

        from application.use_cases.report_use_cases import GenerateAndSaveReportUseCase

        use_case = GenerateAndSaveReportUseCase(
            report_repository=ReportRepositoryImpl(),
            invoice_repository=InvoiceRepositoryImpl(),
            invoice_line_repository=InvoiceLineRepositoryImpl(),
            product_repository=ProductRepositoryImpl(),
            stock_movement_repository=StockMovementRepositoryImpl(),
            business_domain_service=business_domain_service,
            report_dto=report_dto,
            user_id=user_id,
            user_repository=UserRepositoryImpl(),
        )

        use_case.generate_and_save_report_content(report_id)

        connection.close()
        updated_report = report_repository.get_by_id(report_id, force_refresh=True)

        if updated_report and updated_report.status == ReportStatus.COMPLETED:
            logger.info(
                f"Report {report_id} generated successfully - "
                f"type: {report_type}, format: {format}, status: {updated_report.status.value}, "
                f"task_id: {task_id}",
                extra={
                    "report_id": str(report_id),
                    "task_id": task_id,
                    "status": updated_report.status.value,
                },
            )
        else:
            logger.error(
                f"Report {report_id} generation completed but status verification failed - "
                f"expected 'completed', got '{updated_report.status.value if updated_report else 'unknown'}', "
                f"task_id: {task_id}",
                extra={
                    "report_id": str(report_id),
                    "task_id": task_id,
                    "actual_status": updated_report.status.value if updated_report else "unknown",
                },
            )

        return {
            "status": "completed",
            "report_id": str(report_id),
            "report_status": updated_report.status.value if updated_report else "unknown",
            "task_id": task_id,
        }

    except Exception as exc:
        logger.error(
            f"Error generating report {report_id}: {exc}, task_id: {task_id}",
            exc_info=True,
            extra={"report_id": str(report_id), "task_id": task_id},
        )

        try:
            connection.close()
            report = report_repository.get_by_id(report_id, force_refresh=True)
            if report:
                report.status = ReportStatus.FAILED
                report.error_message = str(exc)
                report.updated_at = timezone.now()
                report_repository.update(report)
        except Exception as update_error:
            logger.error(
                f"Failed to update report {report_id} status: {update_error}, "
                f"task_id: {task_id}",
                exc_info=True,
                extra={"report_id": str(report_id), "task_id": task_id},
            )

        raise self.retry(exc=exc) from exc
