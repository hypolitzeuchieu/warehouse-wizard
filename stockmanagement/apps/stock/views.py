from __future__ import annotations

import logging

from apps.authentication.permissions import IsManagerPermission
from apps.authentication.permissions import IsStorekeeper
from apps.stock.models import Category
from apps.stock.models import StockMovement
from apps.stock.models import SubCategory
from apps.stock.serializers import CategorySerializer
from apps.stock.serializers import GetProductCategorySerializer
from apps.stock.serializers import GetProductSubCategorySerializer
from apps.stock.serializers import PaginationQuerySerializer
from apps.stock.serializers import ProductDetailSerializer
from apps.stock.serializers import ProductSerializer
from apps.stock.serializers import ProductUpdateSerializer
from apps.stock.serializers import QuantitySerializer
from apps.stock.serializers import StockMovementSerializer
from apps.stock.serializers import StockSerializer
from apps.stock.serializers import SubCategorySerializer
from apps.stock.serializers import UpdateQuantitySerializer
from apps.stock.service.product_service import ProductService
from apps.stock.service.stock_service import StockService
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    page_size = 10
    max_page_size = 100


class StockViewSet(viewsets.ViewSet):
    """
    A ViewSet for managing inventory operations with logging and robust error handling.
    """
    permission_classes = [IsStorekeeper | IsManagerPermission]
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
                if result.success:
                    return Response(result.data, status=status.HTTP_200_OK)
                return Response(
                    {'error': result.error}, status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                result = self.service.process_stock_movement(
                    product=data['product'],
                    movement_type=data['movement_type'],
                    quantity=data['quantity'],
                    user=request.user,
                    reason=data.get('reason'),
                )
                if result.success:
                    return Response(
                        StockMovementSerializer(result.data).data,
                        status=status.HTTP_201_CREATED
                    )
                return Response(
                    {'error': result.error}, status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        logger.error(
            f"Invalid process movement data provided:{str(serializer.errors)}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Retrieve all movements stock.',
        query_serializer=PaginationQuerySerializer,
        responses={200: StockMovementSerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='stock/movements')
    def get_stock_movements(self, request):
        """
        Retrieve all movements in stock.
        """
        try:
            query_serializer = PaginationQuerySerializer(data=request.query_params)
            query_serializer.is_valid(raise_exception=True)

            paginator = CustomPagination()
            paginator.page_size = query_serializer.validated_data['page_size']

            page = paginator.paginate_queryset(
                queryset=StockMovement.objects.all(),
                request=request,
                view=self
            )
            serializer = StockMovementSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

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

    permission_classes = [IsStorekeeper | IsManagerPermission]

    @swagger_auto_schema(
        operation_description='Retrieve all category.',
        query_serializer=PaginationQuerySerializer,
        responses={200: CategorySerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='categories')
    def get_categories(self, request):
        """
        Retrieve all categories.
        """
        try:
            query_serializer = PaginationQuerySerializer(data=request.query_params)
            query_serializer.is_valid(raise_exception=True)

            page_size = query_serializer.validated_data.get('page_size', 10)
            paginator = CustomPagination()
            paginator.page_size = page_size

            page = paginator.paginate_queryset(
                queryset=Category.objects.all(),
                request=request,
                view=self
            )
            serializer = CategorySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
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
                created_by = request.user
                category = Category.objects.create(
                    name=name,
                    description=description,
                    created_by=created_by,
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
            category = serializer.save()
            category.updated_by = request.user
            category.save()
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
            subcategory_data = serializer.save()
            subcategory_data.updated_by = request.user
            subcategory_data.save()
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
        query_serializer=PaginationQuerySerializer,
        responses={200: SubCategorySerializer, 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['get'], url_path='subcategories')
    def get_subcategories(self, request):
        """
        Retrieve all sub-categories.
        """
        try:
            query_serializer = PaginationQuerySerializer(data=request.query_params)
            query_serializer.is_valid(raise_exception=True)
            page_size = query_serializer.validated_data.get('page_size', 10)
            paginator = CustomPagination()
            paginator.page_size = page_size

            page = paginator.paginate_queryset(
                SubCategory.objects.all(), request, view=self
            )
            serializer = SubCategorySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
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
                created_by = request.user
                subcategory = SubCategory.objects.create(
                    name=data.get('name'),
                    description=data.get('description'),
                    category=category,
                    created_by=created_by,
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
            page_size = serializer.validated_data.get('page_size', 10)
            try:
                products = StockService().get_products_by_category(category_id)
                if products.success:
                    paginator = CustomPagination()
                    paginator.page_size = page_size
                    result_page = paginator.paginate_queryset(products.data, request)
                    serializer = ProductSerializer(result_page, many=True)
                    return paginator.get_paginated_response(serializer.data)
                else:
                    return Response(
                        {'error': products.error},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

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
        operation_description='Retrieve the product by subcategory.',
        responses={200: ProductSerializer, 500: 'Internal Server Error'},
    )
    @action(methods=['GET'], detail=False, url_path='sub/products')
    def get_products_by_subcategory(self, request):
        """
        Retrieve the product by subcategory.
        """
        serializer = GetProductSubCategorySerializer(data=request.query_params)
        if serializer.is_valid():
            subcategory_id = serializer.validated_data.get('subcategory_id')
            page_size = serializer.validated_data.get('page_size', 10)
            try:
                products = StockService().get_products_by_subcategory(
                    subcategory_id
                )
                if products.success:
                    paginator = CustomPagination()
                    paginator.page_size = page_size
                    result_page = paginator.paginate_queryset(products.data, request)
                    serializer = ProductSerializer(result_page, many=True)
                    return paginator.get_paginated_response(serializer.data)
                else:
                    return Response(
                        {'error': products.error},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

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
    permission_classes = [IsStorekeeper | IsManagerPermission]

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
        data = request.data.copy()

        if 'image' in data:
            del data['image']

        if 'image' in request.FILES:
            data['image_file'] = request.FILES['image']

        serializer = ProductSerializer(data=data)
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
                    purchase_price=data.get('purchase_price'),
                    image=data.get('image_file'),
                    on_promotion=data.get('on_promotion', False),
                    promo_price=data.get('promo_price'),
                    promotion_start_date=data.get('promotion_start_date'),
                    promotion_end_date=data.get('promotion_end_date'),
                    min_quantity=data.get('min_quantity'),
                    created_by=request.user,
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
            updated_by = request.user
            response = self.product_service.update_product(
                product_id, serializer.validated_data, updated_by=updated_by
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
        operation_description='Retrieve products with pagination.',
        query_serializer=PaginationQuerySerializer,  # Serializer pour gérer les query params
        responses={200: StockSerializer(many=True), 500: 'Internal Server Error'},
    )
    @action(detail=False, methods=['GET'], url_path='products')
    def get_products(self, request):
        """
        Retrieve all the stock with pagination.
        """
        try:
            query_serializer = PaginationQuerySerializer(data=request.query_params)
            query_serializer.is_valid(raise_exception=True)

            page_size = query_serializer.validated_data.get('page_size', 10)

            stocks = self.product_service.get_all_stock()
            if stocks.success:
                paginator = CustomPagination()
                paginator.page_size = page_size
                result_page = paginator.paginate_queryset(stocks.data, request)
                serializer = StockSerializer(result_page, many=True)
                return paginator.get_paginated_response(serializer.data)

            return Response({'error': stocks.error}, status=status.HTTP_400_BAD_REQUEST)

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

    @swagger_auto_schema(
        operation_description='Add quantity to a product',
        request_body=UpdateQuantitySerializer,
        responses={
            200: ProductSerializer,
            400: 'Bad Request',
            404: 'Product not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['POST'], detail=False, url_path='add-quantity')
    def add_product_quantity(self, request):
        """
        Add quantity to an existing product.
        """
        serializer = UpdateQuantitySerializer(data=request.data)
        if serializer.is_valid():
            product_id = serializer.validated_data.get('product_id')
            quantity = serializer.validated_data.get('quantity')
            updated_by = request.user
            try:
                response = self.product_service.add_product_quantity(
                    product_id, quantity, updated_by
                )
                if response.success:
                    return Response(
                        ProductSerializer(response.data).data,
                        status=status.HTTP_200_OK
                    )
                return Response(
                    {'error': response.error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Error adding product quantity: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description='Reduce quantity from a product',
        request_body=UpdateQuantitySerializer,
        responses={
            200: ProductSerializer,
            400: 'Bad Request',
            404: 'Product not found',
            500: 'Internal Server Error',
        },
    )
    @action(methods=['POST'], detail=False, url_path='reduce-quantity')
    def reduce_product_quantity(self, request):
        """
        Reduce quantity from an existing product.
        """
        serializer = UpdateQuantitySerializer(data=request.data)
        if serializer.is_valid():
            product_id = serializer.validated_data.get('product_id')
            quantity = serializer.validated_data.get('quantity')
            updated_by = request.user
            try:
                response = self.product_service.reduce_product_quantity(
                    product_id, quantity, updated_by
                )
                if response.success:
                    return Response(
                        ProductSerializer(response.data).data,
                        status=status.HTTP_200_OK
                    )
                return Response(
                    {'error': response.error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Error reducing product quantity: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
