from __future__ import annotations

import logging

from apps.authentication.permissions import IsCashier
from apps.authentication.permissions import IsCashierOrManager
from apps.authentication.permissions import IsManagerPermission
from apps.authentication.permissions import IsStorekeeper
from apps.reports.models import Expense
from apps.reports.models import InvoiceArchive
from apps.reports.models import Report
from apps.reports.models import Treasure
from apps.reports.serializers import CreateExpenseSerializer
from apps.reports.serializers import CreateInvoiceSerializer
from apps.reports.serializers import DownloadReportSerializer
from apps.reports.serializers import ExpenseSerializer
from apps.reports.serializers import InventoryQuerySerializer
from apps.reports.serializers import InvoiceArchiveSerializer
from apps.reports.serializers import InvoiceQuerySerializer
from apps.reports.serializers import InvoiceSerializer
from apps.reports.serializers import PayDebtSerializer
from apps.reports.serializers import QueryExpenseSerializer
from apps.reports.serializers import ReportListSerializer
from apps.reports.serializers import ReportQuerySerializer
from apps.reports.serializers import TreasureSerializer
from apps.reports.serializers import UpdateInvoiceSerializer
from apps.reports.service.expense_service import ExpenseService
from apps.reports.service.generateReport import GenerateReportService
from apps.reports.service.invoice_service import ReportService
from apps.stock.views import CustomPagination
from django.http import FileResponse
from django.http import HttpResponse
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)

service = ReportService()


class InvoiceViewSet(viewsets.ViewSet):
    """
    ViewSet for handling reports, invoices, and related operations.
    """

    permission_classes = [IsCashier | IsManagerPermission]

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

    @swagger_auto_schema(
        request_body=UpdateInvoiceSerializer,
        operation_description='Mettre à jour une facture existante',
        responses={
            200: InvoiceSerializer,
            400: 'Bad Request',
            403: 'Permission Denied',
            404: 'Not Found',
            500: 'Internal Server Error'
        },
    )
    @action(methods=['PUT'], detail=False, url_path='update-invoice')
    def update_invoice(self, request):
        serializer = UpdateInvoiceSerializer(data=request.data)
        if serializer.is_valid():
            try:
                data = serializer.validated_data
                invoice_id = data['invoice_id']
                user = request.user

                updated_data = {
                    'client_name': data.get('client_name'),
                    'tax': data.get('tax'),
                    'status': data.get('status'),
                    'reason': data.get('reason'),
                    'advance_paid': data.get('advance_paid'),
                    'due_date': data.get('due_date'),
                    'lines': data.get('lines', []),
                }

                result = service.update_invoice(
                    invoice_id=invoice_id,
                    updated_data=updated_data,
                    user=user
                )

                if not result.success:
                    status_code = status.HTTP_400_BAD_REQUEST
                    if 'permission' in result.error.lower():
                        status_code = status.HTTP_403_FORBIDDEN
                    return Response({'error': result.error}, status=status_code)

                invoice = result.data
                serialized = InvoiceSerializer(invoice)
                return Response(serialized.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Unexpected error occurred during invoice update: {str(e)}")
                return Response(
                    {'error': f'Unexpected error occurred during invoice update: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ArchiveInvoiceVieSet(viewsets.ViewSet):
    """
        ViewSet for handling reports, invoices, and related operations.
    """
    def get_permissions(self):
        if self.action == 'archive_invoice':
            return [IsCashierOrManager()]
        elif self.action in ['get_archives_invoices', 'get_archive_invoice_by_id']:
            return [IsManagerPermission()]
        return [IsManagerPermission()]

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

    permission_classes = [IsManagerPermission | IsCashier | IsStorekeeper]

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
                user = request.user

                report_result = GenerateReportService.generate_report(
                    report_type, user, start_date, end_date,
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

    @swagger_auto_schema(
        operation_description='Retrieve all reports',
        responses={
            200: ReportListSerializer(),
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error',
        }
    )
    @action(methods=['GET'], detail=False, url_path='all-report')
    def get_all_reports(self, request):
        try:
            reports = Report.objects.select_related(
                'inventory_report', 'sales_report'
            ).order_by('-generated_at')

            serializer = ReportListSerializer(
                reports, many=True, context={'request': request}
            )
            logger.info('Reports retrieved successfully.')
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving reports: {str(e)}")
            return Response(
                {'success': False, 'error': 'Failed to retrieve reports.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='Download a report as a PDF file',
        request_body=DownloadReportSerializer,
        responses={
            200: 'Report downloaded successfully (PDF file)',
            400: 'Invalid data or business rule violation.',
            500: 'Internal Server Error',
        }
    )
    @action(methods=['POST'], detail=False, url_path='download-report')
    def download_report(self, request):
        try:
            serializer = DownloadReportSerializer(data=request.data)
            if serializer.is_valid():
                report_id = serializer.validated_data.get('report_id')
                report = GenerateReportService.download_report(report_id)

                if report.success:
                    buffer = report.data['pdf_file']
                    filename = report.data['filename']
                    return FileResponse(
                        buffer,
                        as_attachment=True,
                        filename=filename,
                        content_type='application/pdf'
                    )
                else:
                    return Response(
                        {'success': False, 'error': report.error},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            logger.error(f"Invalid data provided: {serializer.errors}")
            return Response(
                {'success': False, 'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"Error in download_report: {str(e)}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='Retrieve a report by ID',
        query_serializer=DownloadReportSerializer,
        responses={
            200: ReportListSerializer,
            400: 'Invalid data or business rule violation.',
            404: 'Report not found.',
            500: 'Internal Server Error',
        }
    )
    @action(methods=['GET'], detail=False, url_path='report-by-id')
    def get_report_by_id(self, request):
        """
        Retrieve a report by its ID.
        """
        serializer = DownloadReportSerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                report_id = serializer.validated_data.get('report_id')
                report = Report.objects.filter(id=report_id).first()

                if not report:
                    return Response(
                        {'error': 'Report not found.'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                serialized_report = ReportListSerializer(report)
                return Response(serialized_report.data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error retrieving report: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Delete a report by ID',
        query_serializer=DownloadReportSerializer,
        responses={
            204: 'No Content',
            400: 'Invalid data or business rule violation.',
            404: 'Report not found.',
            500: 'Internal Server Error',
        }
    )
    @action(methods=['DELETE'], detail=False, url_path='delete-report')
    def delete_report(self, request):
        """
        Delete a report by its ID.
        """
        serializer = DownloadReportSerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                report_id = serializer.validated_data.get('report_id')
                report = Report.objects.filter(id=report_id).first()

                if not report:
                    return Response(
                        {'error': 'Report not found.'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                report.delete()
                logger.info(f"Report {report_id} deleted successfully.")
                return Response(status=status.HTTP_204_NO_CONTENT)

            except Exception as e:
                logger.error(f"Error deleting report: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        logger.error(f"Invalid data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExpenseViewSet(viewsets.ViewSet):
    permission_classes = [IsStorekeeper | IsCashier | IsManagerPermission]

    @swagger_auto_schema(
        request_body=CreateExpenseSerializer,
        operation_description='Create an expense record',
        responses={
            201: ExpenseSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['POST'], detail=False, url_path='create')
    def create_expense(self, request):
        serializer = CreateExpenseSerializer(data=request.data)
        if serializer.is_valid():
            try:
                created_by = request.user
                amount = serializer.validated_data.get('amount')
                expense_type = serializer.validated_data.get('expense_type')
                reason = serializer.validated_data.get('reason')

                result = ExpenseService.create_expense(
                    amount,
                    expense_type,
                    reason,
                    created_by
                )

                if result.success:
                    return Response(
                        ExpenseSerializer(result.data).data,
                        status=status.HTTP_201_CREATED
                    )
                return Response(
                    {'error': result.error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error in create_expense: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Retrieve all expenses',
        responses={
            200: ExpenseSerializer(many=True),
            400: 'Bad Request',
            403: 'Forbidden',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='all')
    def get_all_expenses(self, request):
        """
        Retrieve all expenses.
        """
        try:
            expenses = Expense.objects.all().order_by('-created_at')
            serializer = ExpenseSerializer(expenses, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error retrieving expenses: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='Retrieve an expense by ID',
        query_serializer=QueryExpenseSerializer,
        responses={
            200: ExpenseSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='expense-by-id')
    def get_expense_by_id(self, request):
        """
        Retrieve an expense by its ID.
        """
        serializer = QueryExpenseSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        expense_id = serializer.validated_data.get('expense_id')

        try:
            expense = Expense.objects.get(id=expense_id)
            serializer = ExpenseSerializer(expense)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Expense.DoesNotExist:
            return Response(
                {'error': 'Expense not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving expense: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='Update an expense record',
        request_body=CreateExpenseSerializer,
        responses={
            200: ExpenseSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['PUT'], detail=True, url_path='update')
    def update_expense(self, request, pk=None):
        """
        Update an existing expense record.
        """
        serializer = CreateExpenseSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            amount = serializer.validated_data.get('amount')
            expense_type = serializer.validated_data.get('expense_type')
            reason = serializer.validated_data.get('reason')
            updated_by = request.user
            expense = ExpenseService.update_expense(
                expense_id=pk,
                new_amount=amount,
                expense_type=expense_type,
                reason=reason,
                updated_by=updated_by
            )
            if expense.success:
                logger.info(f"Expense updated successfully: {expense}")
                return Response(
                    ExpenseSerializer(expense.data).data, status=status.HTTP_200_OK
                )

            logger.error(f'Error updating expense: {expense.error}')
            return Response({'error': expense.error}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error updating expense: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='get exchange summary',
        query_serializer=InventoryQuerySerializer,
        responses={
            200: 'Expense summary retrieved successfully',
            400: 'Bad Request',
            403: 'Forbidden',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='expense-summary')
    def get_expense_summary(self, request):
        """
        Retrieve a summary of expenses based on the provided date range.
        """
        query_serializer = InventoryQuerySerializer(data=request.query_params)
        if query_serializer.is_valid():
            start_date = query_serializer.validated_data.get('start_date')
            end_date = query_serializer.validated_data.get('end_date')
            page_size = query_serializer.validated_data.get('page_size', 10)

            try:
                expenses_summary = ExpenseService.get_expenses_summary(
                    start_date=start_date, end_date=end_date
                )
                if not expenses_summary.success:
                    return Response(
                        {'error': expenses_summary.error},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                summary_data = expenses_summary.data
                categories = summary_data['categories']
                total_amount = summary_data['total']

                paginator = CustomPagination()
                paginator.page_size = page_size
                paginated_categories = paginator.paginate_queryset(categories, request)

                response_data = {
                    'total_amount': total_amount,
                    'categories': paginated_categories
                }

                return paginator.get_paginated_response(response_data)

            except Exception as e:
                logger.error(f"Error retrieving expense summary: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid data provided: {query_serializer.errors}")
        return Response(
            {'error': query_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    @swagger_auto_schema(
        operation_description='Delete an expense record',
        query_serializer=QueryExpenseSerializer,
        responses={
            204: 'No Content',
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['DELETE'], detail=False, url_path='delete')
    def delete_expense(self, request):
        """
        Delete an expense record by its ID.
        """
        serializer = QueryExpenseSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        expense_id = serializer.validated_data.get('expense_id')
        try:
            expense = Expense.objects.get(id=expense_id)
            expense.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Expense.DoesNotExist:
            return Response(
                {'error': 'Expense not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error deleting expense: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='get all treasure balance',
        responses={
            200: TreasureSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='treasure-balance')
    def get_treasure_balance(self, request):
        """
        Retrieve the current treasure balance.
        """
        try:
            balance = Treasure.objects.all()
            serializer = TreasureSerializer(balance, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error retrieving treasure balance: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
