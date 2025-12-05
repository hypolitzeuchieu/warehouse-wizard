"""Report use cases for generating and downloading reports."""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from application.dto.report_dto import ReportCreateDTO, ReportResponseDTO
from application.use_cases.inventory_use_cases import (
    GenerateInventoryReportUseCase,
    GenerateStockReportUseCase,
)
from application.use_cases.sales_use_cases import GenerateSalesReportUseCase
from domain.business.services import BusinessDomainService
from domain.reports.entities import (
    Report,
    ReportFormat,
    ReportStatus,
    ReportType,
)
from domain.reports.repositories import ReportRepository
from domain.users.repositories import UserRepository
from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import ForbiddenError, NotFoundError
from shared.utils.validation import validate_business_access
from tasks.report_tasks import generate_report_task

try:
    from weasyprint import HTML

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

logger = logging.getLogger(__name__)


def _serialize_report_payload(payload: dict) -> dict:
    """Serialize payload to JSON-friendly types."""

    def _serialize(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, list):
            return [_serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: _serialize(val) for key, val in value.items()}
        return value

    return _serialize(copy.deepcopy(payload))


def _sanitize_metadata_for_response(metadata: dict | None) -> dict:
    """Hide heavy/internal metadata fields from API responses."""
    if not metadata:
        return {}
    sanitized = dict(metadata)
    sanitized.pop("payload", None)
    sanitized.pop("business_snapshot", None)
    return sanitized


def _business_snapshot_from_entity(business) -> dict:
    """Capture business details for consistent rendering."""
    if not business:
        return {}
    return {
        "name": business.name,
        "address": business.address,
        "phone": business.phone_number,
        "email": business.email,
        "qr_code_url": business.qr_code_url,
    }


def _parse_iso_datetime(value):
    """Convert ISO datetime strings back to datetime objects when possible."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _prepare_payload_for_render(payload: dict) -> dict:
    """Prepare payload with datetime objects restored for template rendering."""
    prepared = copy.deepcopy(payload)
    for key in ("period_start", "period_end", "generated_at", "generated_start", "generated_end"):
        if key in prepared:
            prepared[key] = _parse_iso_datetime(prepared[key])
    return prepared


# Sentinel value to detect if file_url was provided
class _Sentinel:
    """Sentinel value to detect if file_url was provided."""


_SENTINEL = _Sentinel()


def _report_to_dto(
    report: Report, file_url: str | None | _Sentinel = _SENTINEL
) -> ReportResponseDTO:
    """
    Convert report entity to DTO (shared utility function).

    Args:
        report: Report entity to convert
        file_url: Optional file URL. If not provided (default), uses report.file_url.
                  If explicitly set to None, uses None.

    Returns:
        ReportResponseDTO instance
    """
    final_file_url = report.file_url if file_url is _SENTINEL else file_url
    return ReportResponseDTO(
        id=report.id,
        business_id=report.business_id,
        report_type=report.report_type.value,
        format=report.format.value,
        status=report.status.value,
        start_date=report.start_date,
        end_date=report.end_date,
        file_url=final_file_url,
        file_size=report.file_size,
        generated_by=report.generated_by,
        error_message=report.error_message,
        metadata=_sanitize_metadata_for_response(report.metadata),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _render_report_html(
    report_payload: dict, business_info: dict, generated_by_name: str | None
) -> str:
    """Render report HTML using stored payload and business snapshot."""
    payload_for_render = _prepare_payload_for_render(report_payload)
    generated_ts = payload_for_render.get("generated_at") or timezone.now()

    context = {
        "report": payload_for_render,
        "business": business_info,
        "generated_by_name": generated_by_name,
        "generated_at": generated_ts,
    }
    return render_to_string("reports/report.html", context)


def _generate_pdf_from_html(html_content: str) -> bytes:
    """Generate PDF bytes from HTML content."""
    if not WEASYPRINT_AVAILABLE:
        raise BaseAPIException(
            detail="WeasyPrint is required for PDF generation",
            code="PDF_GENERATION_UNAVAILABLE",
            status_code=500,
        )
    try:
        return HTML(string=html_content).write_pdf()
    except Exception as exc:
        logger.error("Error generating PDF report: %s", exc, exc_info=True)
        raise BaseAPIException(
            detail=f"Failed to generate PDF report: {str(exc)}",
            code="PDF_GENERATION_ERROR",
            status_code=500,
        ) from exc


class GenerateAndSaveReportUseCase:
    """Use case for generating and saving a report."""

    def __init__(
        self,
        report_repository: ReportRepository,
        invoice_repository,
        invoice_line_repository,
        product_repository,
        stock_movement_repository,
        business_domain_service: BusinessDomainService,
        report_dto: ReportCreateDTO,
        user_id: UUID,
        user_repository: UserRepository | None = None,
    ) -> None:
        """Initialize use case."""
        self.report_repository = report_repository
        self.invoice_repository = invoice_repository
        self.invoice_line_repository = invoice_line_repository
        self.product_repository = product_repository
        self.stock_movement_repository = stock_movement_repository
        self.business_domain_service = business_domain_service
        self.business_id = report_dto.business_id
        self.user_id = user_id
        self.report_type = ReportType(report_dto.report_type)
        self.format = ReportFormat(report_dto.format)
        self.start_date = self._ensure_timezone_aware(report_dto.start_date)
        self.end_date = self._ensure_timezone_aware(report_dto.end_date)
        self.business = None
        self.user_repository = user_repository
        self.generated_by_label: str | None = None

    @staticmethod
    def _ensure_timezone_aware(dt: datetime | None) -> datetime | None:
        """Ensure datetime is timezone-aware."""
        if dt is None:
            return None
        if timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt

    @staticmethod
    def _build_base_payload(report_dto, report_type: str, title: str) -> dict:
        """Build base payload structure common to all reports."""
        return {
            "report_type": report_type,
            "title": title,
            "business_id": str(report_dto.business_id),
            "period_start": report_dto.period_start,
            "period_end": report_dto.period_end,
            "generated_at": report_dto.generated_at,
        }

    def _build_sales_payload(self, report_dto) -> dict:
        """Build sales report payload."""
        payload = self._build_base_payload(report_dto, "sales", "Sales Report")
        payload.update(
            {
                "summary": [
                    {"label": "Total Revenue", "value": str(report_dto.total_revenue)},
                    {"label": "Total Invoices", "value": report_dto.total_invoices},
                    {"label": "Items Sold", "value": report_dto.total_items_sold},
                    {
                        "label": "Average Invoice Value",
                        "value": str(report_dto.average_invoice_value),
                    },
                ],
                "payment_breakdown": [
                    {
                        "payment_method": item.payment_method,
                        "total_amount": str(item.total_amount),
                        "number_of_invoices": item.number_of_invoices,
                    }
                    for item in report_dto.sales_by_payment_method
                ],
                "status_breakdown": [
                    {
                        "status": item.status,
                        "total_amount": str(item.total_amount),
                        "number_of_invoices": item.number_of_invoices,
                    }
                    for item in report_dto.sales_by_status
                ],
                "top_products": [
                    {
                        "product_id": str(p.product_id),
                        "product_name": p.product_name,
                        "total_quantity_sold": p.total_quantity_sold,
                        "total_revenue": str(p.total_revenue),
                        "number_of_sales": p.number_of_sales,
                    }
                    for p in report_dto.top_products
                ],
                "top_customers": [
                    {
                        "customer_id": str(c.customer_id) if c.customer_id else None,
                        "customer_name": c.customer_name,
                        "total_purchases": str(c.total_purchases),
                        "number_of_invoices": c.number_of_invoices,
                    }
                    for c in report_dto.top_customers
                ],
            }
        )
        return payload

    def _build_inventory_payload(self, report_dto) -> dict:
        """Build inventory report payload."""
        payload = self._build_base_payload(report_dto, "inventory", "Inventory Report")
        payload.update(
            {
                "summary": [
                    {"label": "Total Products", "value": report_dto.total_products},
                    {
                        "label": "Inventory Value",
                        "value": str(report_dto.total_inventory_value),
                    },
                    {"label": "Low Stock Items", "value": report_dto.low_stock_products},
                    {"label": "Expired Products", "value": report_dto.expired_products},
                ],
                "products": [
                    {
                        "product_id": str(p.product_id),
                        "product_name": p.product_name,
                        "current_quantity": p.current_quantity,
                        "unit_price": str(p.unit_price),
                        "total_value": str(p.total_value),
                        "is_low_stock": p.is_low_stock,
                        "is_expired": p.is_expired,
                        "expiry_date": p.expiry_date,
                    }
                    for p in report_dto.products
                ],
                "stock_movements_summary": [
                    {
                        "movement_type": s.movement_type,
                        "total_quantity": s.total_quantity,
                        "number_of_movements": s.number_of_movements,
                        "products_affected": s.products_affected,
                    }
                    for s in report_dto.stock_movements_summary
                ],
            }
        )
        return payload

    @staticmethod
    def _build_product_info_dict(product) -> dict:
        """Build product info dictionary (shared across reports)."""
        return {
            "product_id": str(product.product_id),
            "product_name": product.product_name,
            "current_quantity": product.current_quantity,
            "min_quantity": product.min_quantity,
            "unit_price": str(product.unit_price),
            "total_value": str(product.total_value),
            "is_low_stock": product.is_low_stock,
            "is_expired": product.is_expired,
            "expiry_date": product.expiry_date,
        }

    def _build_stock_payload(self, report_dto) -> dict:
        """Build stock report payload."""
        payload = self._build_base_payload(report_dto, "stock", "Stock Report")
        payload.update(
            {
                "summary": [
                    {
                        "label": "Current Stock Value",
                        "value": str(report_dto.current_stock_value),
                    },
                    {"label": "Movements In", "value": report_dto.stock_movements_in},
                    {"label": "Movements Out", "value": report_dto.stock_movements_out},
                    {"label": "Net Change", "value": report_dto.net_stock_change},
                ],
                "products_by_stock_level": {
                    "low": [
                        self._build_product_info_dict(p)
                        for p in report_dto.products_by_stock_level.get("low", [])
                    ],
                    "normal": [
                        self._build_product_info_dict(p)
                        for p in report_dto.products_by_stock_level.get("normal", [])
                    ],
                    "high": [
                        self._build_product_info_dict(p)
                        for p in report_dto.products_by_stock_level.get("high", [])
                    ],
                },
                "stock_movements_by_type": [
                    {
                        "movement_type": s.movement_type,
                        "total_quantity": s.total_quantity,
                        "number_of_movements": s.number_of_movements,
                        "products_affected": s.products_affected,
                    }
                    for s in report_dto.stock_movements_by_type
                ],
            }
        )
        return payload

    def _validate_report_permission(self) -> None:
        """Validate user has permission to generate the requested report type."""
        permission_map = {
            ReportType.SALES: self.business_domain_service.can_generate_sales_report,
            ReportType.INVENTORY: self.business_domain_service.can_generate_inventory_report,
            ReportType.STOCK: self.business_domain_service.can_generate_stock_report,
        }

        check_permission = permission_map.get(self.report_type)
        if not check_permission:
            raise ValueError(f"Unknown report type: {self.report_type}")

        if not check_permission(self.business_id, self.user_id):
            report_type_name = self.report_type.value.lower()
            raise ForbiddenError(
                detail=f"You don't have permission to generate {report_type_name} reports for this business",
                code="PERMISSION_DENIED",
            )

    @transaction.atomic
    def execute(self) -> ReportResponseDTO:
        """Execute report generation and saving."""
        self._validate_report_permission()

        self._ensure_date_range()
        self.generated_by_label = self._get_generated_by_label()

        business = self.business_domain_service.get_business(self.business_id)
        if not business:
            raise NotFoundError(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
            )
        self.business = business

        report_id = uuid4()
        metadata = {}
        if self.generated_by_label:
            metadata["generated_by_name"] = self.generated_by_label

        report = Report(
            id=report_id,
            business_id=self.business_id,
            report_type=self.report_type,
            format=self.format,
            status=ReportStatus.GENERATING,
            start_date=self.start_date,
            end_date=self.end_date,
            file_path=None,
            file_url=None,
            file_size=None,
            generated_by=self.user_id,
            error_message=None,
            metadata=metadata,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        report = self.report_repository.create(report)

        try:
            generate_report_task.delay(
                report_id=report_id,
                business_id=self.business_id,
                user_id=self.user_id,
                report_type=self.report_type.value,
                format=self.format.value,
                start_date=self.start_date.isoformat() if self.start_date else None,
                end_date=self.end_date.isoformat() if self.end_date else None,
            )

            logger.info(
                f"Report {report_id} generation queued for async processing "
                f"(type: {self.report_type.value}, format: {self.format.value})"
            )
            return self._to_dto(report)

        except Exception as celery_error:
            logger.error(
                f"Failed to queue report generation task for {report_id}: {str(celery_error)}. "
                f"Celery worker must be running for report generation.",
                exc_info=True,
                extra={"report_id": str(report_id)},
            )

            report.status = ReportStatus.FAILED
            report.error_message = (
                f"Failed to queue report generation: {str(celery_error)}. "
                f"Please ensure Celery worker is running."
            )
            report.updated_at = timezone.now()
            self.report_repository.update(report)

            raise BaseAPIException(
                detail="Report generation service is unavailable. Please try again later.",
                code="CELERY_UNAVAILABLE",
                status_code=503,
            ) from celery_error

    def generate_and_save_report_content(self, report_id: UUID) -> ReportResponseDTO:
        """
        Generate report content and update the existing report.

        This method is called by the Celery task to actually generate the report content.
        It should only be called from within an async task context.

        Args:
            report_id: ID of the report to generate content for

        Returns:
            ReportResponseDTO with completed report information
        """
        report = self.report_repository.get_by_id(report_id)
        if not report:
            raise NotFoundError(
                detail="Report not found",
                code="REPORT_NOT_FOUND",
            )

        if not self.business:
            self.business = self.business_domain_service.get_business(self.business_id)
            if not self.business:
                raise NotFoundError(
                    detail="Business not found",
                    code="BUSINESS_NOT_FOUND",
                )

        if not self.generated_by_label:
            self.generated_by_label = self._get_generated_by_label()

        try:
            if self.report_type == ReportType.SALES:
                report_payload = self._generate_sales_report()
            elif self.report_type == ReportType.INVENTORY:
                report_payload = self._generate_inventory_report()
            elif self.report_type == ReportType.STOCK:
                report_payload = self._generate_stock_report()
            else:
                raise ValueError(f"Unknown report type: {self.report_type}")

            serialized_payload = _serialize_report_payload(report_payload)
            business_snapshot = _business_snapshot_from_entity(self.business)

            updated_metadata: dict[str, Any] = report.metadata or {}
            updated_metadata["payload"] = serialized_payload
            updated_metadata["business_snapshot"] = business_snapshot
            if self.generated_by_label:
                updated_metadata["generated_by_name"] = self.generated_by_label

            report.metadata = updated_metadata
            report.status = ReportStatus.COMPLETED
            report.file_path = None
            report.file_url = None
            report.file_size = None
            report.updated_at = timezone.now()
            report = self.report_repository.update(report)

            return self._to_dto(report)

        except Exception as e:
            logger.error(f"Error generating report {report_id}: {str(e)}", exc_info=True)
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            report.updated_at = timezone.now()
            self.report_repository.update(report)
            raise BaseAPIException(
                detail=f"Failed to generate report: {str(e)}",
                code="REPORT_GENERATION_ERROR",
                status_code=500,
            ) from e

    def _generate_sales_report(self) -> bytes | str | dict:
        """Generate sales report content."""
        use_case = GenerateSalesReportUseCase(
            invoice_repository=self.invoice_repository,
            invoice_line_repository=self.invoice_line_repository,
            product_repository=self.product_repository,
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        report_dto = use_case.execute()
        payload = self._build_sales_payload(report_dto)
        return self._prepare_report_payload(payload)

    def _generate_inventory_report(self) -> bytes | str | dict:
        """Generate inventory report content."""
        use_case = GenerateInventoryReportUseCase(
            product_repository=self.product_repository,
            stock_movement_repository=self.stock_movement_repository,
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        report_dto = use_case.execute()
        payload = self._build_inventory_payload(report_dto)
        return self._prepare_report_payload(payload)

    def _generate_stock_report(self) -> bytes | str | dict:
        """Generate stock report content."""
        use_case = GenerateStockReportUseCase(
            stock_movement_repository=self.stock_movement_repository,
            product_repository=self.product_repository,
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        report_dto = use_case.execute()
        payload = self._build_stock_payload(report_dto)
        return self._prepare_report_payload(payload)

    def _ensure_date_range(self) -> None:
        """Ensure start and end dates have sensible defaults."""
        now = timezone.now()
        default_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        default_end = default_start + timedelta(days=1) - timedelta(microseconds=1)

        if self.start_date is None:
            self.start_date = default_start
        if self.end_date is None:
            self.end_date = default_end

        if self.start_date > self.end_date:
            self.start_date, self.end_date = self.end_date, self.start_date

    def _get_generated_by_label(self) -> str:
        """Resolve the name/email of the user who generated the report."""
        if not self.user_repository:
            return str(self.user_id)
        user = self.user_repository.get_by_id(self.user_id)
        if not user:
            return str(self.user_id)
        return user.name or user.email or str(user.id)

    def _prepare_report_payload(self, payload: dict) -> dict:
        """Ensure payload contains period and generator information."""
        payload["period_start"] = payload.get("period_start") or self.start_date
        payload["period_end"] = payload.get("period_end") or self.end_date
        payload["generated_by"] = self.generated_by_label
        payload["generated_start"] = self.start_date
        payload["generated_end"] = self.end_date
        return payload

    def _to_dto(self, report: Report) -> ReportResponseDTO:
        """Convert report entity to DTO."""
        return _report_to_dto(report, file_url=None)


class DownloadReportUseCase:
    """Use case for downloading a report by ID."""

    def __init__(
        self,
        report_repository: ReportRepository,
        business_domain_service: BusinessDomainService,
        report_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.report_repository = report_repository
        self.business_domain_service = business_domain_service
        self.report_id = report_id
        self.user_id = user_id

    def execute(self) -> tuple[bytes | str, str, str]:
        """
        Execute report download.

        Returns:
            Tuple of (content, content_type, filename)
        """
        report = self.report_repository.get_by_id(self.report_id)
        if not report:
            raise NotFoundError(
                detail="Report not found",
                code="REPORT_NOT_FOUND",
            )

        if report.status != ReportStatus.COMPLETED:
            raise BaseAPIException(
                detail=f"Report is not ready. Status: {report.status.value}",
                code="REPORT_NOT_READY",
                status_code=400,
            )
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=report.business_id,
            user_id=self.user_id,
            error_message="You don't have access to this report",
        )

        metadata = report.metadata or {}
        payload = metadata.get("payload")

        if payload:
            business_snapshot = metadata.get("business_snapshot")
            if not business_snapshot:
                business = self.business_domain_service.get_business(report.business_id)
                if not business:
                    raise NotFoundError(
                        detail="Business not found",
                        code="BUSINESS_NOT_FOUND",
                    )
                business_snapshot = _business_snapshot_from_entity(business)

            html_content = _render_report_html(
                report_payload=payload,
                business_info=business_snapshot,
                generated_by_name=metadata.get("generated_by_name"),
            )

            created_at = getattr(report, "created_at", None)
            if created_at:
                timestamp_str = created_at.strftime("%Y%m%d_%H%M%S")
            else:
                timestamp_str = "report"

            content: bytes | str
            if report.format == ReportFormat.PDF:
                content = _generate_pdf_from_html(html_content)
                content_type = "application/pdf"
                filename = f"{report.report_type.value}_report_{timestamp_str}.pdf"
            else:
                content = html_content
                content_type = "text/html"
                filename = f"{report.report_type.value}_report_{timestamp_str}.html"

            return content, content_type, filename

        raise BaseAPIException(
            detail="Report content is no longer available",
            code="REPORT_FILE_NOT_FOUND",
            status_code=404,
        )


class DeleteReportUseCase:
    """Use case for deleting a report."""

    def __init__(
        self,
        report_repository: ReportRepository,
        business_domain_service: BusinessDomainService,
        report_id: UUID,
        user_id: UUID,
    ) -> None:
        self.report_repository = report_repository
        self.business_domain_service = business_domain_service
        self.report_id = report_id
        self.user_id = user_id

    def execute(self) -> None:
        """Delete the report."""
        report = self.report_repository.get_by_id(self.report_id)
        if not report:
            raise NotFoundError(
                detail="Report not found",
                code="REPORT_NOT_FOUND",
            )

        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=report.business_id,
            user_id=self.user_id,
            error_message="You don't have access to this report",
        )

        self.report_repository.delete(report.id)


class ListReportsUseCase:
    """Use case for listing reports for a business."""

    def __init__(
        self,
        report_repository: ReportRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        report_type: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> None:
        self.report_repository = report_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.report_type = ReportType(report_type) if report_type else None
        self.status = ReportStatus(status) if status else None
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit

    def execute(self) -> list[ReportResponseDTO]:
        """Return reports after verifying access."""
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        reports = self.report_repository.get_by_business(
            business_id=self.business_id,
            report_type=self.report_type.value if self.report_type else None,
            status=self.status.value if self.status else None,
            start_date=self.start_date,
            end_date=self.end_date,
            limit=self.limit,
        )
        return [self._to_dto(report) for report in reports]

    def _to_dto(self, report: Report) -> ReportResponseDTO:
        """Convert entity to DTO."""
        return _report_to_dto(report, file_url=report.file_url)
