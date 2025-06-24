# dashboard/views.py
from __future__ import annotations

import logging

from authentication.permissions import IsManagerPermission
from dashboard.serializers import DashboardStatsSerializer
from dashboard.serializers import InventoryDataDashboardSerializer
from dashboard.serializers import LimitQuerySerializer
from dashboard.serializers import PeriodQuerySerializer
from dashboard.serializers import ProductsDataSerializer
from dashboard.serializers import RecentSaleSerializer
from dashboard.serializers import SalesDataSerializer
from dashboard.service import DashboardService
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class DashboardViewSet(viewsets.ViewSet):
    """
    ViewSet for dashboard data.
    """

    permission_classes = [IsManagerPermission]

    @swagger_auto_schema(
        query_serializer=PeriodQuerySerializer,
        operation_description='Get main dashboard statistics',
        responses={200: DashboardStatsSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='stats')
    def get_dashboard_stats(self, request):
        """
        Get main KPI statistics for the dashboard.
        """
        serializer = PeriodQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get('start_date')
                end_date = serializer.validated_data.get('end_date')
                result = DashboardService.get_dashboard_stats(start_date, end_date)

                if result.success:
                    response_serializer = DashboardStatsSerializer(data=result.data)
                    if response_serializer.is_valid():
                        logger.info(
                            'Dashboard stats fetched successfully:', response_serializer.data
                        )
                        return Response(response_serializer.data, status=status.HTTP_200_OK)

                    logger.error('Invalid Data:', response_serializer.errors)
                    return Response(
                        response_serializer.errors,
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                logger.error(f"Error in get_dashboard_stats: {str(result.error)}")
                return Response(
                    {'error': result.error}, status=status.HTTP_400_BAD_REQUEST
                )

            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid period data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=PeriodQuerySerializer,
        operation_description='Get sales data for charts',
        responses={200: SalesDataSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='sales')
    def get_sales_data(self, request):
        """
        Get sales data for charts and visualizations.
        """
        serializer = PeriodQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get('start_date')
                end_date = serializer.validated_data.get('end_date')
                result = DashboardService.get_sales_data(start_date, end_date)

                if result.success:
                    response_serializer = SalesDataSerializer(data=result.data)
                    if response_serializer.is_valid():
                        logger.info(
                            'Sales data fetched successfully:',
                            response_serializer.data
                        )
                        return Response(response_serializer.data, status=status.HTTP_200_OK)

                    logger.error('Invalid Data:', response_serializer.errors)
                    return Response(
                        response_serializer.errors,
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                logger.error(f"Error in get_sales_data: {str(result.error)}")
                return Response({'error': result.error}, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid period data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=PeriodQuerySerializer,
        operation_description='Get product performance data',
        responses={200: ProductsDataSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='top-sales-products')
    def get_products_data(self, request):
        """
        Get product performance data.
        """
        serializer = PeriodQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            try:
                start_date = serializer.validated_data.get('start_date')
                end_date = serializer.validated_data.get('end_date')
                result = DashboardService.get_top_selling_products(start_date, end_date)

                if result.success:
                    response_serializer = ProductsDataSerializer(data=result.data)
                    if response_serializer.is_valid():
                        logger.info(
                            'Products data fetched successfully:',
                            response_serializer.data
                        )
                        return Response(response_serializer.data, status=status.HTTP_200_OK)

                    logger.error('Invalid Data:', response_serializer.errors)
                    return Response(
                        response_serializer.errors,
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                logger.error(f"Error in get_products_data: {str(result.error)}")
                return Response({'error': result.error}, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid period data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Get inventory status data',
        responses={
            200: InventoryDataDashboardSerializer,
            500: 'Internal Server Error'
        },
    )
    @action(detail=False, methods=['GET'], url_path='inventory')
    def get_inventory_data(self, request):
        """
        Get inventory status data.
        """
        try:
            result = DashboardService.get_inventory_data()

            if result.success:
                response_serializer = InventoryDataDashboardSerializer(data=result.data)
                if response_serializer.is_valid():
                    logger.info(
                        'Inventory data fetched successfully:',
                        response_serializer.data
                    )
                    return Response(response_serializer.data, status=status.HTTP_200_OK)

                logger.error('Invalid Data:', response_serializer.errors)
                return Response(
                    response_serializer.errors,
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            logger.error('Error in get_inventory_data:', result.error)
            return Response({'error': result.error}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='Get recent sales',
        query_serializer=LimitQuerySerializer,
        responses={
            200: RecentSaleSerializer,
            400: 'Bad Request',
            500: 'Internal Server Error'
        }
    )
    @action(methods=['GET'], detail=False, url_path='recent-sales')
    def get_recent_sales(self, request):
        serializer = LimitQuerySerializer(data=request.query_params)
        if serializer.is_valid():
            limit = serializer.validated_data.get('limit')
            try:
                result = DashboardService.get_recent_sales(limit)

                if result.success:
                    response_serializer = RecentSaleSerializer(
                        data=result.data, many=True
                    )
                    if response_serializer.is_valid():
                        logger.info(
                            'Recent sales data fetched successfully:',
                            response_serializer.data
                        )
                        return Response(response_serializer.data, status=status.HTTP_200_OK)

                    logger.error('Invalid Data:', response_serializer.errors)
                    return Response(
                        response_serializer.errors,
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                logger.error(f"Error in get_recent_sales: {str(result.error)}")
                return Response(
                    {'error': result.error}, status=status.HTTP_400_BAD_REQUEST
                )

            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid period data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
