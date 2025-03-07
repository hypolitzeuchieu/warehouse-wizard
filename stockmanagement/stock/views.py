from __future__ import annotations

import logging

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from stock.models import Category
from stock.models import StockMovement
from stock.models import SubCategory
from stock.serializers import CategorySerializer
from stock.serializers import GetProductCategorySerializer
from stock.serializers import GetProductSubCategorySerializer
from stock.serializers import ProductDetailSerializer
from stock.serializers import ProductSerializer
from stock.serializers import ProductUpdateSerializer
from stock.serializers import QuantitySerializer
from stock.serializers import StockMovementSerializer
from stock.serializers import StockSerializer
from stock.serializers import SubCategorySerializer
from stock.service import ProductService
from stock.service import StockService

logger = logging.getLogger(__name__)


class StockViewSet(viewsets.ViewSet):
    """
    A ViewSet for managing inventory operations with logging and robust error handling.
    """

    service = StockService()

    # --- Stocks ---

    @swagger_auto_schema(
        query_serializer=QuantitySerializer,
        operation_description='Retrieve the product by category.',
        responses={200: ProductSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['get'])
    def get_stock_quantity(self, request):
        """
        Retrieve a product quantity in stock.
        """
        serializer = QuantitySerializer(data=request.query_params)
        if serializer.is_valid():
            product_id = serializer.validated_data.get('product_id')
            try:
                result = self.service.get_stock_quantity(product_id)
                if result['status'] == 'success':
                    return Response(result, status=status.HTTP_200_OK)
                else:
                    return Response(result, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response(
                    {'error': str(e)}, status=status.HTTP_400_BAD_REQUEST
                )

        logger.error(f"Invalid param provided:{str(serializer.errors)}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # --- Mouvements de stock ---

    @swagger_auto_schema(
        operation_description='Create or update a product. '
                              'If the product exists, increment its stock.',
        request_body=StockMovementSerializer,
        responses={
            201: StockMovementSerializer,
            400: 'Bad Request',
            404: 'Sector not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['POST'], detail=False, url_path='movement-stock')
    def process_stock_movement(self, request):
        """
        Handle stock movements for entry, exit, or adjustment operations.
        """
        serializer = StockMovementSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            try:
                result, status_code = self.service.process_stock_movement(
                    product=data['product'],
                    movement_type=data['movement_type'],
                    quantity=data['quantity'],
                    user=request.user,
                    reason=data.get('reason'),
                )
                return Response(
                    StockMovementSerializer(result).data, status=status_code
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e)}, status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return Response(
                    {'error': f"An unexpected error occurred. {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        logger.error(
            f"Invalid process movement data provided:{str(serializer.errors)}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Retrieve all movements stock.',
        responses={200: StockSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='stock/movements')
    def get_stock_movements(self, request):
        """
        Retrieve all movements in stock.
        """
        try:
            movements = StockMovement.objects.all()
            serializer = StockMovementSerializer(movements, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return Response(
                {'error': str(e)}, status=status.HTTP_400_BAD_REQUEST
            )


class CategoryViewSet(viewsets.ViewSet):
    """
        A ViewSet for managing categories operations.
    """
    # --- Catégories ---

    @swagger_auto_schema(
        operation_description='Retrieve all category.',
        responses={200: CategorySerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='categories')
    def get_categories(self, request):
        """
        Retrieve all categories.
        """
        try:
            categories = Category.objects.all()
            serializer = CategorySerializer(categories, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return Response(
                {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='Create category.',
        request_body=CategorySerializer,
        responses={
            201: CategorySerializer,
            400: 'Bad Request',
            404: 'Sector not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['POST'], detail=False, url_path='category/create')
    def create_category(self, request):
        """
        create new category.
        """
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            try:
                name = serializer.validated_data.get('name')
                description = serializer.validated_data.get('description', '')
                category = Category.objects.create(
                    name=name,
                    description=description,
                )
                serializer = CategorySerializer(category)
                return Response(
                    serializer.data, status=status.HTTP_201_CREATED
                )
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        logger.error(f"Invalid category data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Update category.',
        request_body=CategorySerializer,
        responses={
            200: CategorySerializer,
            400: 'Bad Request',
            404: 'Category not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['PUT'], detail=True, url_path='category/update')
    def update_category(self, request, pk=None):
        """
        Update an existing category.
        """
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Delete category.',
        responses={204: 'Category deleted', 404: 'Category not found'},
    )
    @action(methods=['DELETE'], detail=True, url_path='category/delete')
    def delete_category(self, request, pk=None):
        """
        Delete a category.
        """
        try:
            category = Category.objects.get(pk=pk)
            category.delete()
            return Response(
                {'message': 'Category deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Category.DoesNotExist:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        operation_description='Retrieve category details.',
        responses={
            200: CategorySerializer,
            404: 'Category not found',
            500: 'Internal Server Error',
        },
    )
    @action(detail=True, methods=['GET'], url_path='category/detail')
    def get_category_detail(self, request, pk=None):
        """
        Retrieve details of a specific category.
        """
        try:
            category = Category.objects.get(pk=pk)
            serializer = CategorySerializer(category)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Category.DoesNotExist:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    # ---Sub category-----

    @swagger_auto_schema(
        operation_description='Update subcategory.',
        request_body=SubCategorySerializer,
        responses={
            200: SubCategorySerializer,
            400: 'Bad Request',
            404: 'Subcategory not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['PUT'], detail=True, url_path='subcategory/update')
    def update_subcategory(self, request, pk=None):
        """
        Update an existing subcategory.
        """
        try:
            subcategory = SubCategory.objects.get(pk=pk)
        except SubCategory.DoesNotExist:
            return Response(
                {'error': 'Subcategory not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SubCategorySerializer(
            subcategory, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Delete subcategory.',
        responses={204: 'Subcategory deleted', 404: 'Subcategory not found'},
    )
    @action(methods=['DELETE'], detail=True, url_path='subcategory/delete')
    def delete_subcategory(self, request, pk=None):
        """
        Delete a subcategory.
        """
        try:
            subcategory = SubCategory.objects.get(pk=pk)
            subcategory.delete()
            return Response(
                {'message': 'Subcategory deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except SubCategory.DoesNotExist:
            return Response(
                {'error': 'Subcategory not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        operation_description='Retrieve subcategory details.',
        responses={
            200: SubCategorySerializer,
            404: 'Subcategory not found',
            500: 'Internal Server Error',
        },
    )
    @action(detail=True, methods=['GET'], url_path='subcategory/detail')
    def get_subcategory_detail(self, request, pk=None):
        """
        Retrieve details of a specific subcategory.
        """
        try:
            subcategory = SubCategory.objects.get(pk=pk)
            serializer = SubCategorySerializer(subcategory)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SubCategory.DoesNotExist:
            return Response(
                {'error': 'Subcategory not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @swagger_auto_schema(
        operation_description='Retrieve all category.',
        responses={200: SubCategorySerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['get'], url_path='subcategories')
    def get_subcategories(self, request):
        """
        Retrieve all sub-categories.
        """
        try:
            subcategories = SubCategory.objects.all()
            serializer = SubCategorySerializer(subcategories, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_description='Create subcategory.',
        request_body=SubCategorySerializer,
        responses={
            201: SubCategorySerializer,
            400: 'Bad Request',
            404: 'Sector not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['POST'], detail=False, url_path='subcategory/create')
    def create_subcategory(self, request):
        """
        create new subcategory.
        """
        serializer = SubCategorySerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            try:
                category = Category.objects.get(id=data.get('category_id'))
                subcategory = SubCategory.objects.create(
                    name=data.get('name'),
                    description=data.get('description'),
                    category=category,
                )
                serializer = SubCategorySerializer(subcategory)
                return Response(
                    serializer.data, status=status.HTTP_201_CREATED
                )
            except Category.DoesNotExist as e:
                logger.error(f"category not found: {str(e)}")
                return Response(
                    {'error': str(e)}, status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        logger.error(f"Invalid subcategory data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=GetProductCategorySerializer,
        operation_description='Retrieve the product by category.',
        responses={200: ProductSerializer, 500: 'Internal Server Error'},
    )
    @action(methods=['GET'], detail=False, url_path='products')
    def get_products_by_category(self, request):
        """
        Retrieve the product by category.
        """
        serializer = GetProductCategorySerializer(data=request.query_params)
        if serializer.is_valid():
            category_id = serializer.validated_data.get('category_id')
            try:
                products = StockService().get_products_by_category(category_id)
                result = ProductSerializer(products, many=True)
                return Response(result.data, status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        logger.error(
            f"Invalid category_id data provided:{str(serializer.errors)}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=GetProductSubCategorySerializer,
        operation_description='Retrieve the product by category.',
        responses={200: ProductSerializer, 500: 'Internal Server Error'},
    )
    @action(methods=['GET'], detail=False, url_path='products')
    def get_products_by_subcategory(self, request):
        """
        Retrieve the product by subcategory.
        """
        serializer = GetProductSubCategorySerializer(data=request.query_params)
        if serializer.is_valid():
            subcategory_id = serializer.validated_data.get('subcategory_id')
            try:
                products = StockService().get_products_by_subcategory(
                    subcategory_id
                )
                result = ProductSerializer(products, many=True)
                return Response(result.data, status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        logger.error(
            f"Invalid subcategory_id data provided:{str(serializer.errors)}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductViewSet(viewsets.ViewSet):
    """
        A ViewSet for handling Product operations.
    """

    product_service = ProductService

    @swagger_auto_schema(
        operation_description='Create a new product while managing stock.',
        request_body=ProductSerializer,
        responses={
            201: ProductSerializer,
            400: 'Bad Request',
            404: 'Category not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['POST'], detail=False, url_path='create')
    def create_product(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            try:
                response = self.product_service.create_product(
                    name=data.get('name'),
                    description=data.get('description'),
                    unit_price=data.get('unit_price'),
                    category_id=data.get('category_id'),
                    subcategory_id=data.get('subcategory_id', ''),
                    expired_date=data.get('expiry_date'),
                    quantity=data.get('quantity'),
                    image=data.get('image'),
                    on_promotion=data.get('on_promotion', False),
                    promo_price=data.get('promo_price'),
                    promotion_start_date=data.get('promotion_start_date'),
                    promotion_end_date=data.get('promotion_end_date'),
                    min_quantity=data.get('min_quantity'),
                )
                if response.success:
                    return Response(
                        ProductSerializer(response.data).data, status=status.HTTP_201_CREATED
                    )
                return Response(
                    {'error': response.error}, status=status.HTTP_400_BAD_REQUEST
                )

            except Exception as e:
                logger.error(f"An unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        logger.error(f"Invalid product data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Update an existing product.',
        request_body=ProductUpdateSerializer,
        responses={
            200: ProductSerializer,
            400: 'Bad Request',
            404: 'Product not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['PUT'], detail=False, url_path='update')
    def update_product(self, request):
        serializer = ProductUpdateSerializer(data=request.data)
        if serializer.is_valid():
            product_id = serializer.validated_data.pop('product_id')
            response = self.product_service.update_product(
                product_id, serializer.validated_data
            )
            if response.success:
                return Response(
                    ProductSerializer(response.data).data, status=status.HTTP_200_OK
                )
            return Response(
                {'error': response.error}, status=status.HTTP_400_BAD_REQUEST
            )
        logger.error(f"Invalid product_id data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Delete a product by ID.',
        query_serializer=ProductDetailSerializer,
        responses={
            204: 'No Content',
            400: 'Bad Request',
            404: 'Product not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['DELETE'], detail=False, url_path='delete')
    def delete_product(self, request):
        serializer = ProductDetailSerializer(data=request.query_params)
        if serializer.is_valid():
            product_id = serializer.validated_data.get('product_id')
            try:
                response = self.product_service.delete_product(product_id)
                if response.success:
                    return Response(
                        {'message': response.data}, status=status.HTTP_204_NO_CONTENT
                    )
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid product_id data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        query_serializer=ProductDetailSerializer,
        operation_description='Retrieve the product by id.',
        responses={
            200: ProductSerializer,
            404: 'Product not found',
            400: 'Bad Request',
            500: 'Internal Server Error'
        },
    )
    @action(methods=['GET'], detail=False, url_path='detail')
    def get_product_detail(self, request):
        """
        Retrieve the product by id.
        """
        serializer = ProductDetailSerializer(data=request.query_params)
        if serializer.is_valid():
            product_id = serializer.validated_data.get('product_id')
            try:
                response = self.product_service.get_product_by_id(product_id)
                if response.success:
                    return Response(
                        ProductSerializer(response.data).data, status=status.HTTP_200_OK
                    )
                return Response(
                    {'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        logger.error(f"Invalid product_id data provided: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Retrieve products.',
        responses={200: StockSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='products')
    def get_products(self, request):
        """
        Retrieve all the stock.
        """
        try:
            stocks = self.product_service.get_all_stock()
            if stocks.success:
                serializer = StockSerializer(stocks.data, many=True)
                return Response(serializer.data)
            return Response({'error': stocks.error}, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return Response(
                {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        operation_description='Retrieve the product by expiry date.',
        responses={200: ProductSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='expiry_date')
    def get_products_by_expiry_date(self, request):
        """
        Retrieve the product by expiry date.
        """
        try:
            result = self.product_service.get_products_by_expiry_date()
            print('result', result)
            if result.success:
                serializer = ProductSerializer(
                    result.data['expired_products'], many=True
                )
                near_expiry_product = ProductSerializer(
                    result.data['near_expiry'], many=True
                )
                return Response(
                    {
                        'expired_products': serializer.data,
                        'expired_product_count': result.data['count'],
                        'near_expiry_products': near_expiry_product.data,
                        'near_expiry_products_count': result.data['near_expiry_count'],
                    }
                )
            return Response({'error': result.error}, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            return Response(
                {'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
