from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from authentication.models import User
from reports.serializers import (
    InvoiceSerializer,
    InventoryReportSerializer,
    SalesReportSerializer,
    NotificationSerializer,
    SalesSummaryQuerySerializer,
    InventoryQuerySerializer,
    CreateInvoiceSerializer,
)
from reports.service import ReportService
import logging

logger = logging.getLogger(__name__)


class ReportsViewSet(viewsets.ViewSet):
    """
    ViewSet for handling reports, invoices, and related operations.
    """

    service = ReportService()

    # --- Invoice Endpoints ---
    @swagger_auto_schema(
        request_body=CreateInvoiceSerializer,
        operation_description="Process and create a new invoice.",
        responses={201: InvoiceSerializer, 400: "Bad Request", 500: "Internal Server Error"},
    )
    @action(methods=["POST"], detail=False, url_path="create-invoice")
    def create_invoice(self, request):
        """
        Process and create a new invoice based on the provided data.
        """
        serializer = CreateInvoiceSerializer(data=request.data)
        if serializer.is_valid():
            try:
                data = serializer.validated_data
                user = User.objects.get(id="b7d7811fd49e4146aaa01843ade401b4") # user = request.user
                invoice = self.service.process_invoice(data=data, user=user)
                serializer = InvoiceSerializer(invoice)
                return Response(serializer.data, status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error in create_invoice: {str(e)}")
                return Response(
                    {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "invoice_id", openapi.IN_PATH, description="ID of the invoice to export", type=openapi.TYPE_INTEGER
            )
        ],
        operation_description="Export an invoice to PDF format.",
        responses={200: "PDF file", 404: "Not Found", 500: "Internal Server Error"},
    )
    @action(methods=["GET"], detail=True, url_path="export-pdf")
    def export_invoice_to_pdf(self, request, pk=None):
        """
        Export an invoice to PDF format by ID.
        """
        try:
            pdf_file = self.service.export_invoice_to_pdf(pk)
            response = Response(pdf_file.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = f"attachment; filename=invoice_{pk}.pdf"
            return response
        except Exception as e:
            logger.error(f"Error in export_invoice_to_pdf: {str(e)}")
            return Response(
                {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # --- Inventory Report Endpoints ---
    @swagger_auto_schema(
        request_body=InventoryQuerySerializer,
        operation_description="Generate an inventory report for a specific date range.",
        responses={201: InventoryReportSerializer, 500: "Internal Server Error"},
    )
    @action(methods=["POST"], detail=False, url_path="generate-inventory-report")
    def generate_inventory_report(self, request):
        """
        Generate an inventory report for a specific date range.
        """
        serializer = InventoryQuerySerializer(data=request.data)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get("start_date")
                end_date = serializer.validated_data.get("end_date")
                user = User.objects.get(id="b7d7811fd49e4146aaa01843ade401b4")  # user = request.user
                report = self.service.generate_inventory_report(
                    start_date=start_date,end_date=end_date, user=user
                )
                serializer = InventoryReportSerializer(report)
                return Response(serializer.data, status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error in generate_inventory_report: {str(e)}")
                return Response(
                    {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=InventoryQuerySerializer,
        operation_description="Retrieve inventory data for a specific date range.",
        responses={200: "Inventory data", 500: "Internal Server Error"},
    )
    @action(methods=["GET"], detail=False, url_path="inventory-data")
    def get_inventory_data(self, request):
        """
        Retrieve inventory data for a specific date range.
        """
        serializer = InventoryQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get("start_date")
                end_date = serializer.validated_data.get("end_date")

                inventory_data = self.service.get_inventory_data(
                    start_date=start_date,end_date=end_date
                )

                return Response(inventory_data, status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Error in get_inventory_data: {str(e)}")
                return Response(
                    {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    # --- Sales Report Endpoints ---
    @swagger_auto_schema(
        query_serializer=InventoryQuerySerializer,
        operation_description="Retrieve a sales summary for a specific period.",
        responses={200: "Sales summary data", 400: "Bad Request", 500: "Internal Server Error"},
    )
    @action(methods=["GET"], detail=False, url_path="sales-summary")
    def get_sales_summary(self, request):
        """
        Retrieve a sales summary for a specific period.
        """
        serializer = InventoryQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get("start_date")
                end_date = serializer.validated_data.get("end_date")

                user = User.objects.get(id="b7d7811fd49e4146aaa01843ade401b4") #request.user
                summary = self.service.get_sales_summary(
                    start_date=start_date, end_date=end_date, user=user
                )
                return Response(summary, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in get_sales_summary: {str(e)}")
                return Response(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        request_body=SalesSummaryQuerySerializer,
        operation_description="Create or retrieve a daily sales report.",
        responses={201: SalesReportSerializer, 500: "Internal Server Error"},
    )
    @action(methods=["POST"], detail=False, url_path="create-sales-report")
    def create_sales_report(self, request):
        """
        Create or retrieve a daily sales report.
        """
        serializer = SalesSummaryQuerySerializer(data=request.data)
        if serializer.is_valid():
            try:
                date = serializer.validated_data.get("date")
                user = User.objects.get(id="b7d7811fd49e4146aaa01843ade401b4") #request.user
                report = self.service.create_sales_report(date=date, user=user)
                serializer = SalesReportSerializer(report)
                return Response(serializer.data, status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error in create_sales_report: {str(e)}")
                return Response(
                    {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    # --- Notification Endpoints ---
    @swagger_auto_schema(
        operation_description="Retrieve all notifications.",
        responses={200: NotificationSerializer(many=True), 500: "Internal Server Error"},
    )
    @action(methods=["GET"], detail=False, url_path="notifications")
    def get_notifications(self, request):
        """
        Retrieve all notifications for stock levels and other alerts.
        """
        try:
            notifications = self.service.get_all_notifications()
            serializer = NotificationSerializer(notifications, many=True)
            return Response(serializer.data, status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in get_notifications: {str(e)}")
            return Response(
                {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
            )
