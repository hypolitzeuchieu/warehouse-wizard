from __future__ import annotations

import logging

from authentication.permissions import IsManagerPermission
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from reports.models import InvoiceArchive
from reports.serializers import CreateInvoiceSerializer
from reports.serializers import InventoryQuerySerializer
from reports.serializers import InventoryReportSerializer
from reports.serializers import InvoiceQuerySerializer
from reports.serializers import InvoiceSerializer
from reports.serializers import PayDebtSerializer
from reports.serializers import SalesReportSerializer
from reports.serializers import SalesSummaryQuerySerializer
from reports.service import ReportService
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


logger = logging.getLogger(__name__)

service = ReportService()


class ReportsViewSet(viewsets.ViewSet):
    """
    ViewSet for handling reports, invoices, and related operations.
    """

    # --- Invoice Endpoints ---
    @swagger_auto_schema(
        request_body=CreateInvoiceSerializer,
        operation_description='Process and create a new invoice.',
        responses={
            201: InvoiceSerializer,
            400: 'Bad Request',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['POST'], detail=False, url_path='create-invoice')
    def create_invoice(self, request):
        """
        Process and create a new invoice based on the provided data.
        """
        serializer = CreateInvoiceSerializer(data=request.data)
        if serializer.is_valid():
            try:
                data = serializer.validated_data
                user = request.user
                result = service.process_invoice(data=data, user=user)

                if not result.success:
                    return Response({'error': result.error}, status.HTTP_400_BAD_REQUEST)

                invoice = result.data
                serialized_invoice = InvoiceSerializer(invoice)
                return Response(serialized_invoice.data, status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Error in create_invoice: {str(e)}")
                return Response(
                    {'error': invoice['error']}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=InvoiceQuerySerializer,
        operation_description='Export an invoice to PDF format.',
        responses={
            200: 'PDF file',
            404: 'Not Found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['GET'], detail=False, url_path='export-pdf')
    def export_invoice_to_pdf(self, request):
        """
        Export an invoice to PDF format by invoice_id.
        """
        serializer = InvoiceQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                invoice_id = serializer.validated_data.get('invoice_id')

                pdf_file = service.export_invoice_to_pdf(invoice_id)

                if not pdf_file:
                    return Response(
                        {'error': 'Invoice not found'}, status.HTTP_404_NOT_FOUND
                    )

                response = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = (f'attachment; '
                                                   f'filename=invoice_{invoice_id}.pdf')
                return response
            except Exception as e:
                logger.error(f"Error in export_invoice_to_pdf: {str(e)}")
                return Response(
                    {'error': str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f'invalid data: {serializer.errors}')
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    # --- Inventory Report Endpoints ---
    @swagger_auto_schema(
        request_body=InventoryQuerySerializer,
        operation_description='Generate an inventory report for a specific date range.',
        responses={
            201: InventoryReportSerializer,
            500: 'Internal Server Error',
        },
    )
    @action(
        methods=['POST'], detail=False, url_path='generate-inventory-report'
    )
    def generate_inventory_report(self, request):
        """
        Generate an inventory report for a specific date range.
        """
        serializer = InventoryQuerySerializer(data=request.data)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get('start_date')
                end_date = serializer.validated_data.get('end_date')
                user = request.user
                report = service.generate_inventory_report(
                    start_date=start_date, end_date=end_date, user=user
                )
                if not report.success:
                    return Response({'error': report.error}, status.HTTP_400_BAD_REQUEST)

                serializer = InventoryReportSerializer(report.data)
                return Response(serializer.data, status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error in generate_inventory_report: {str(e)}")
                return Response(
                    {'error': str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=InventoryQuerySerializer,
        operation_description='Retrieve inventory data for a specific date range.',
        responses={200: 'Inventory data', 500: 'Internal Server Error'},
    )
    @action(methods=['GET'], detail=False, url_path='inventory-data')
    def get_inventory_data(self, request):
        """
        Retrieve inventory data for a specific date range.
        """
        serializer = InventoryQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get('start_date')
                end_date = serializer.validated_data.get('end_date')

                inventory_data = service.get_inventory_data(
                    start_date=start_date, end_date=end_date
                )

                if not inventory_data.success:
                    return Response(
                        {'error': inventory_data.error}, status.HTTP_400_BAD_REQUEST
                    )

                return Response(inventory_data.data, status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in get_inventory_data: {str(e)}")
                return Response(
                    {'error': str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    # --- Sales Report Endpoints ---
    @swagger_auto_schema(
        query_serializer=InventoryQuerySerializer,
        operation_description='Retrieve a sales summary for a specific period.',
        responses={
            200: 'Sales summary data',
            400: 'Bad Request',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['GET'], detail=False, url_path='sales-summary')
    def get_sales_summary(self, request):
        """
        Retrieve a sales summary for a specific period.
        """
        serializer = InventoryQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get('start_date')
                end_date = serializer.validated_data.get('end_date')

                user = request.user
                summary = service.get_sales_summary(
                    start_date=start_date, end_date=end_date, user=user
                )
                if not summary.success:
                    return Response(
                        {'error': summary.error}, status.HTTP_400_BAD_REQUEST
                    )
                return Response(summary.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in get_sales_summary: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        request_body=SalesSummaryQuerySerializer,
        operation_description='Create or retrieve a daily sales report.',
        responses={201: SalesReportSerializer, 500: 'Internal Server Error'},
    )
    @action(methods=['POST'], detail=False, url_path='create-sales-report')
    def create_sales_report(self, request):
        """
        Create or retrieve a daily sales report.
        """
        serializer = SalesSummaryQuerySerializer(data=request.data)
        if serializer.is_valid():
            try:
                date = serializer.validated_data.get('date')
                user = request.user
                report = service.create_sales_report(date=date, user=user)

                if not report.success:
                    return Response({'error': report.error}, status.HTTP_400_BAD_REQUEST)

                serializer = SalesReportSerializer(report.data)
                return Response(serializer.data, status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Error in create_sales_report: {str(e)}")
                return Response(
                    {'error': str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        request_body=PayDebtSerializer,
        operation_description='Process a payment for an outstanding invoice.',
        responses={
            200: 'Payment processed successfully.',
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error'
        },
    )
    @action(methods=['POST'], detail=False, url_path='pay-debt')
    def pay_debt(self, request):
        """
        Process a payment for an outstanding invoice.
        """
        serializer = PayDebtSerializer(data=request.data)
        if serializer.is_valid():
            try:
                invoice_id = serializer.validated_data.get('invoice_id')
                amount = serializer.validated_data.get('amount')

                response = service.pay_debt(invoice_id=invoice_id, amount=amount)

                if not response.success:
                    return Response(
                        {'error': response.error}, status=status.HTTP_400_BAD_REQUEST
                    )
                logger.info(f"Payment processed successfully for invoice {invoice_id}.")
                return Response(response.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in pay_debt: {str(e)}")
                return Response(
                    {'error': 'An internal error occurred.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        request_body=InvoiceQuerySerializer,
        operation_description='Archive an invoice.',
        responses={
            200: 'Invoice archived successfully.',
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error'
        },
    )
    @action(methods=['POST'], detail=False, url_path='archive-invoice')
    def archive_invoice(self, request):
        """
        Archive an invoice.
        """
        serializer = InvoiceQuerySerializer(data=request.data)
        if serializer.is_valid():
            try:
                invoice_id = serializer.validated_data.get('invoice_id')

                response = service.archive_and_delete_invoice(invoice_id=invoice_id)

                if not response.success:
                    return Response(
                        {'error': response.error}, status=status.HTTP_400_BAD_REQUEST
                    )
                logger.info(f"Invoice archived successfully for invoice {invoice_id}.")
                return Response(response.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in archive_invoice: {str(e)}")
                return Response(
                    {'error': 'An internal error occurred.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=InventoryQuerySerializer,
        operation_description='Retrieve all invoices.',
        responses={
            200: InvoiceSerializer,
            400: 'Bad Request',
            500: 'Internal Server Error'
        },
    )
    @action(methods=['GET'], detail=False, url_path='invoices')
    def get_invoices(self, request):
        """
        Retrieve all invoices.
        """
        serializer = InventoryQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            start_date = serializer.validated_data.get('start_date')
            end_date = serializer.validated_data.get('end_date')
            try:
                invoices = service.get_invoices(
                    start_date=start_date, end_date=end_date
                )
                if not invoices.success:
                    return Response(
                        {'error': invoices.error}, status=status.HTTP_400_BAD_REQUEST
                    )
                serializer = InvoiceSerializer(invoices, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ArchiveInvoiceVieSet(viewsets.ViewSet):
    """
        ViewSet for handling reports, invoices, and related operations.
    """
    permission_classes = [IsAuthenticated, IsManagerPermission]

    @swagger_auto_schema(
        query_serializer=InventoryQuerySerializer,
        operation_description='Retrieve Archive invoice',
        responses={
            200: 'Invoice retrieve successfully.',
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='all-archive-invoice')
    def get_archives_invoices(self, request):
        """
        Retrieve Archive invoice
        """
        serializer = InventoryQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get('start_date')
                end_date = serializer.validated_data.get('end_date')
                invoices = InvoiceArchive.objects.filter(
                    created_at__range=(start_date, end_date)
                )
                if not invoices.success:
                    return Response(
                        {'error': invoices.error},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                serializer = InvoiceSerializer(invoices, many=True)
                logger.info('Invoice retrieve successfully.')
                return Response(serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in archive_invoice: {str(e)}")
                return Response(
                    {'error': 'An internal error occurred.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=InvoiceQuerySerializer,
        operation_description='Retrieve Archive invoice by id',
        responses={
            200: 'Invoice retrieve successfully.',
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='archive-invoice-by-id')
    def get_archive_invoice_by_id(self, request):
        """
        Retrieve Archive invoice by id
        """
        serializer = InvoiceQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                invoice_id = serializer.validated_data.get('invoice_id')
                invoice = InvoiceArchive.objects.filter(id=invoice_id).first()
                serializer = InvoiceSerializer(invoice)
                logger.info('Invoice retrieve successfully.')
                return Response(serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in archive_invoice: {str(e)}")
                return Response(
                    {'error': 'An internal error occurred.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
