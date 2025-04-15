from __future__ import annotations

import logging

from authentication.permissions import IsCashier
from authentication.permissions import IsManagerPermission
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from reports.models import InvoiceArchive
from reports.serializers import CreateInvoiceSerializer
from reports.serializers import InventoryQuerySerializer
from reports.serializers import InvoiceArchiveSerializer
from reports.serializers import InvoiceQuerySerializer
from reports.serializers import InvoiceSerializer
from reports.serializers import PayDebtSerializer
from reports.serializers import ReportQuerySerializer
from reports.service import GenerateReportService
from reports.service import ReportService
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from stock.views import CustomPagination

logger = logging.getLogger(__name__)

service = ReportService()


class InvoiceViewSet(viewsets.ViewSet):
    """
    ViewSet for handling reports, invoices, and related operations.
    """

    permission_classes = [IsAuthenticated, IsCashier]

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
                    {f'An internal error occurred:{str(e)}'},
                    status.HTTP_500_INTERNAL_SERVER_ERROR
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

                if pdf_file.success:
                    response = HttpResponse(
                        pdf_file.data.getvalue(), content_type='application/pdf'
                    )
                    response['Content-Disposition'] = (f'attachment; '
                                                       f'filename=invoice_{invoice_id}.pdf')
                    return response

                return Response(
                    {'error': 'Invoice not found'}, status.HTTP_404_NOT_FOUND
                )

            except Exception as e:
                logger.error(f"Error in export_invoice_to_pdf: {str(e)}")
                return Response(
                    {'error': str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f'invalid data: {serializer.errors}')
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
                    {f'An internal error occurred:{str(e)}'},
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
        query_serializer = InventoryQuerySerializer(data=request.query_params)
        if query_serializer.is_valid():
            start_date = query_serializer.validated_data.get('start_date')
            end_date = query_serializer.validated_data.get('end_date')
            try:
                invoices = service.get_invoices(
                    start_date=start_date, end_date=end_date
                )
                if not invoices.success:
                    return Response(
                        {'error': invoices.error}, status=status.HTTP_400_BAD_REQUEST
                    )
                paginator = CustomPagination()  #
                page_size = query_serializer.validated_data.get('page_size', 10)
                paginator.page_size = page_size

                result_page = paginator.paginate_queryset(invoices.data, request)
                serializer = InvoiceSerializer(result_page, many=True)
                return paginator.get_paginated_response(serializer.data)

            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {query_serializer.errors}")
        return Response(query_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ArchiveInvoiceVieSet(viewsets.ViewSet):
    """
        ViewSet for handling reports, invoices, and related operations.
    """
    permission_classes = [IsAuthenticated, IsManagerPermission]

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
                    {f'An internal error occurred:{str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=InventoryQuerySerializer,
        operation_description='Retrieve Archive invoice',
        responses={
            200: InvoiceArchiveSerializer,
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='all-archive-invoice')
    def get_archives_invoices(self, request):
        """
        Retrieve Archive invoice
        """
        query_serializer = InventoryQuerySerializer(data=request.query_params)
        if query_serializer.is_valid():
            try:
                start_date = query_serializer.validated_data.get('start_date')
                end_date = query_serializer.validated_data.get('end_date')
                invoices = service.get_archives_invoices(start_date, end_date)
                if not invoices.success:
                    return Response(
                        {'error': invoices.error},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                paginator = CustomPagination()  #
                page_size = query_serializer.validated_data.get('page_size', 10)
                paginator.page_size = page_size

                result_page = paginator.paginate_queryset(invoices.data, request)
                serializer = InvoiceArchiveSerializer(result_page, many=True)
                logger.info('Invoice retrieve successfully.')
                return paginator.get_paginated_response(serializer.data)

            except Exception as e:
                logger.error(f"Error in archive_invoice: {str(e)}")
                return Response(
                    {f'An internal error occurred:{str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {query_serializer.errors}")
        return Response(query_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=InvoiceQuerySerializer,
        operation_description='Retrieve Archive invoice by id',
        responses={
            200: InvoiceArchiveSerializer,
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
                serializer = InvoiceArchiveSerializer(invoice)
                logger.info('Invoice retrieve successfully.')
                return Response(serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error in archive_invoice: {str(e)}")
                return Response(
                    {f'An internal error occurred:{str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GeneralReportViewSet(viewsets.ViewSet):

    permission_classes = [IsAuthenticated, IsCashier]

    @swagger_auto_schema(
        query_serializer=ReportQuerySerializer,
        operation_description='Retrieve General report',
        responses={
            200: 'Sucessfully retrieved report',
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error',
        },

    )
    @action(methods=['GET'], detail=False, url_path='generate')
    def get_general_report(self, request):
        """
        Retrieve General report based on type and date range.
        """
        query_serializer = ReportQuerySerializer(data=request.query_params)
        if query_serializer.is_valid():
            try:
                report_type = query_serializer.validated_data.get('report_type')
                start_date = query_serializer.validated_data.get('start_date')
                end_date = query_serializer.validated_data.get('end_date')
                period = query_serializer.validated_data.get('period')
                user = request.user

                report_result = GenerateReportService.generate_report(
                    report_type, user, start_date, end_date, period
                )

                response_data = {
                    'success': report_result.success
                }

                if report_result.success:
                    response_data['data'] = report_result.data
                else:
                    response_data['error'] = report_result.error

                # Sérialiser directement la réponse sans contexte supplémentaire
                return Response(
                    response_data,
                    status=status.HTTP_200_OK
                    if report_result.success else status.HTTP_400_BAD_REQUEST
                )

            except Exception as e:
                logger.error(f"Error in get_general_report: {str(e)}")
                return Response(
                    {'success': False, 'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f"Invalid data provided: {query_serializer.errors}")
        return Response(
            {'success': False, 'error': query_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
