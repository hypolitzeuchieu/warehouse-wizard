"""Report ViewSet for managing reports."""

from __future__ import annotations

from uuid import UUID

from django.http import HttpResponse
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.report_use_cases import (
    DeleteReportUseCase,
    DownloadReportUseCase,
    GenerateAndSaveReportUseCase,
    ListReportsUseCase,
    report_to_dto,
)
from domain.business.services import BusinessDomainService
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
from presentation.serializers.report_serializers import (
    ReportListQuerySerializer,
    ReportResponseSerializer,
    SalesReportQuerySerializer,
)
from shared.security.query_params_validator import QueryParamsValidator
from shared.views.base_viewset import BaseViewSet


class ReportViewSet(BaseViewSet):
    """ViewSet for report management."""

    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        """Disable content negotiation for download endpoint to avoid conflict with 'format' query param."""
        if self.action == "download_report":
            renderers = self.get_renderers()
            return (renderers[0], renderers[0].media_type)
        return super().perform_content_negotiation(request, force)

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List reports",
        operation_description="List generated reports for a business within an optional date range.",
        query_serializer=ReportListQuerySerializer,
        responses={
            200: ReportResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Reports"],
    )
    def list(self, request: Request) -> Response:
        """List stored reports for a business (standard REST endpoint)."""
        serializer = ReportListQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        business_id = serializer.validated_data["business_id"]
        if not self._get_business_domain_service().user_has_access(business_id, request.user.id):
            return self.error(
                message="You don't have access to this business",
                status_code=status.HTTP_403_FORBIDDEN,
                code="PERMISSION_DENIED",
            )

        try:
            use_case = ListReportsUseCase(
                report_repository=ReportRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                report_type=serializer.validated_data.get("report_type"),
                status=serializer.validated_data.get("status"),
                start_date=serializer.validated_data.get("start_date"),
                end_date=serializer.validated_data.get("end_date"),
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
            )
            reports = use_case.execute()

            return self.paginated_response(
                request=request,
                queryset=reports,
                serializer_class=ReportResponseSerializer,
                message="Reports retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Retrieve report",
        operation_description="Retrieve a report by its ID with all metadata.",
        responses={
            200: ReportResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Report not found",
        },
        tags=["Reports"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Retrieve a report by ID."""
        try:
            report_repository = ReportRepositoryImpl()
            report = report_repository.get_by_id(pk, force_refresh=True)

            if not report:
                return self.error(
                    message="Report not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="REPORT_NOT_FOUND",
                )

            if not self._get_business_domain_service().user_has_access(
                report.business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this report",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            # Convert report entity to DTO
            report_dto = report_to_dto(report)

            return self.serialized_response(
                serializer_class=ReportResponseSerializer,
                data=report_dto,
                message="Report retrieved successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Generate and save report",
        operation_description="Generate a report (sales, inventory, or stock) for a business within a date range and save it.",
        query_serializer=SalesReportQuerySerializer,
        responses={
            202: ReportResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            500: "Internal server error",
        },
        tags=["Reports"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="generate",
    )
    def generate_report(self, request: Request) -> Response:
        """Generate and save a report (sales, inventory, or stock) for a business."""
        try:
            query_serializer = SalesReportQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            report_dto = query_serializer.to_dto()

            use_case = GenerateAndSaveReportUseCase(
                report_repository=ReportRepositoryImpl(),
                invoice_repository=InvoiceRepositoryImpl(),
                invoice_line_repository=InvoiceLineRepositoryImpl(),
                product_repository=ProductRepositoryImpl(),
                stock_movement_repository=StockMovementRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                report_dto=report_dto,
                user_id=request.user.id,
                user_repository=UserRepositoryImpl(),
            )
            report_dto = use_case.execute()

            message = "Report generation initiated successfully"
            if report_dto.status == "generating":
                message = (
                    "Report generation initiated. The report is being generated in the background."
                )

            return self.serialized_response(
                serializer_class=ReportResponseSerializer,
                data=report_dto,
                message=message,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Download report",
        operation_description="Download a previously generated report file from S3. The file format is determined by the report format specified during generation.",
        responses={
            200: openapi.Response(
                "Report file (PDF or Word)",
                schema=openapi.Schema(type=openapi.TYPE_FILE),
            ),
            400: "Bad Request",
            403: "Permission denied",
            404: "Report not found or file not available",
        },
        tags=["Reports"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="download",
    )
    def download_report(self, request: Request, pk: UUID) -> Response:
        """Download a report by ID. Format is determined by the report itself."""
        try:
            use_case = DownloadReportUseCase(
                report_repository=ReportRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                report_id=pk,
                user_id=request.user.id,
            )
            content, content_type, filename = use_case.execute()

            response = HttpResponse(content, content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get report status",
        operation_description="Get report generation status with progress percentage.",
        responses={
            200: openapi.Response(
                "Report status",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "report_id": openapi.Schema(
                            type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID
                        ),
                        "status": openapi.Schema(
                            type=openapi.TYPE_STRING, enum=["generating", "completed", "failed"]
                        ),
                        "progress_percentage": openapi.Schema(
                            type=openapi.TYPE_INTEGER, description="Progress percentage (0-100)"
                        ),
                        "estimated_time_remaining_seconds": openapi.Schema(
                            type=openapi.TYPE_INTEGER,
                            description="Estimated time remaining in seconds",
                            allow_null=True,
                        ),
                        "created_at": openapi.Schema(
                            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                        ),
                        "updated_at": openapi.Schema(
                            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                        ),
                        "error_message": openapi.Schema(type=openapi.TYPE_STRING, allow_null=True),
                    },
                ),
            ),
            404: "Report not found",
            403: "Permission denied",
        },
        tags=["Reports"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="status",
    )
    def get_report_status(self, request: Request, pk: UUID) -> Response:
        """Get report generation status with progress percentage."""
        try:
            report_repository = ReportRepositoryImpl()
            report = report_repository.get_by_id(pk, force_refresh=True)

            if not report:
                return self.error(
                    message="Report not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="REPORT_NOT_FOUND",
                )

            if not self._get_business_domain_service().user_has_access(
                report.business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this report",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            progress_percentage = 0
            estimated_time_remaining = None

            if report.status.value == "completed":
                progress_percentage = 100
                estimated_time_remaining = 0
            elif report.status.value == "failed":
                progress_percentage = 0
                estimated_time_remaining = None
            elif report.status.value == "generating":
                time_elapsed = timezone.now() - report.created_at
                estimated_total_time = 20

                if time_elapsed.total_seconds() < estimated_total_time:
                    progress_percentage = min(
                        int((time_elapsed.total_seconds() / estimated_total_time) * 100), 95
                    )
                    estimated_time_remaining = max(
                        int(estimated_total_time - time_elapsed.total_seconds()), 1
                    )
                else:
                    progress_percentage = 95
                    estimated_time_remaining = 5

            return self.success(
                message="Report status retrieved successfully",
                data={
                    "report_id": str(pk),
                    "status": report.status.value,
                    "progress_percentage": progress_percentage,
                    "estimated_time_remaining_seconds": estimated_time_remaining,
                    "created_at": report.created_at.isoformat(),
                    "updated_at": report.updated_at.isoformat(),
                    "error_message": report.error_message,
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete report",
        operation_description="Delete a previously generated report by its ID.",
        responses={
            204: "Report deleted",
            400: "Bad Request",
            403: "Permission denied",
            404: "Report not found",
        },
        tags=["Reports"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete a report by ID."""
        try:
            use_case = DeleteReportUseCase(
                report_repository=ReportRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                report_id=pk,
                user_id=request.user.id,
            )
            use_case.execute()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return self.handle_exception(e)
