from __future__ import annotations

import logging

from apps.notifications.service import NotificationService
from apps.reports.service.invoice_service import ReportService
from apps.stock.models import Category
from apps.stock.models import Product
from apps.stock.models import Stock
from apps.stock.models import StockMovement
from apps.stock.models import SubCategory
from apps.stock.service.entities import StockServiceResponse
from apps.stock.service.product_service import ProductService
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

reports_service = ReportService()
notif_service = NotificationService()


class StockService:
    """
    Service for handling stock-related operations.
    """

    @staticmethod
    def get_products_by_category(category_id) -> StockServiceResponse:
        """
        Get all products in a specific category.
        """
        try:
            products = Product.objects.filter(category_id=category_id)
            logger.info(
                f"Retrieved {products.count()} products for category: {category_id}"
            )
            return StockServiceResponse(success=True, data=products)

        except Category.DoesNotExist:
            logger.error(f"Category with id {category_id} not found.")
            return StockServiceResponse(
                success=False, error=f"Category with id {category_id} not found."
            )
        except Exception as e:
            logger.error(f"Error in get_products_by_category: {str(e)}")
            return StockServiceResponse(
                success=False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_products_by_subcategory(subcategory_id) -> StockServiceResponse:
        """
        Get all products in a specific category.
        """
        try:
            products = Product.objects.filter(subcategory_id=subcategory_id)
            logger.info(
                f"Retrieved {products.count()} products for category: {subcategory_id}"
            )
            return StockServiceResponse(success=True, data=products)

        except SubCategory.DoesNotExist:
            logger.error(f"subcategory with id {subcategory_id} not found.")
            return StockServiceResponse(
                success=False, error=f"Category with id {subcategory_id} not found."
            )

        except Exception as e:
            logger.error(f"Error in get_products_by_subcategory: {str(e)}")
            return StockServiceResponse(
                success=False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_stock_quantity(product_id) -> StockServiceResponse:
        """
        Get the current stock quantity of a product in a specific category and subcategory.
        """
        try:
            product_response = ProductService.get_product_by_id(product_id)
            if not product_response.success:
                return StockServiceResponse(success=False, error=product_response.error)

            product = product_response.data
            category = product.category
            subcategory = product.subcategory

            stock = Stock.objects.get(
                product_id=product_id,
                category=category,
                subcategory=subcategory,
            )

            if stock.product.quantity == 0:
                logger.info(
                    f"Product ID {product_id} is out of stock in category ID {category},"
                    f" subcategory ID {subcategory}"
                )
                return StockServiceResponse(
                    success=True,
                    data={'quantity': 0, 'message': 'Product is out of stock.'}
                )

            logger.info(
                f"Stock quantity for product {stock.product.name} is {stock.product.quantity}"
            )
            return StockServiceResponse(
                success=True,
                data={
                    'message': 'Stock retrieved successfully.',
                    'quantity': stock.product.quantity,
                }
            )
        except Stock.DoesNotExist:
            logger.warning(f"No stock record found for product ID {product_id},")
            return StockServiceResponse(
                success=False,
                error='Stock record not found for the given product and category.'
            )
        except Exception as e:
            logger.error(f"Error in get_stock_quantity: {str(e)}")
            return StockServiceResponse(
                success=False,
                error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def update_stock(product, quantity) -> StockServiceResponse:
        try:
            product_response = ProductService.get_product_by_id(product.id)
            if not product_response.success:
                return StockServiceResponse(success=False, error=product_response.error)

            product = product_response.data  # Access the actual product instance
            category = product.category
            subcategory = product.subcategory

            stock, created = Stock.objects.get_or_create(
                product=product,
                category=category,
                subcategory=subcategory,
            )
            if stock.product.quantity + quantity < 0:
                logger.warning(
                    f"Insufficient stock for product {product.name}, "
                    f"category {category.name},subcategory "
                    f"{subcategory.name if subcategory else 'None'}. "
                    f"Current quantity: {stock.quantity}, "
                    f"Attempted adjustment: {quantity}."
                )
                return StockServiceResponse(
                    success=False,
                    error=f"Insufficient stock for this operation."
                          f" Current quantity: {stock.quantity}."
                )
            product.quantity += quantity
            product.save()

            return StockServiceResponse(
                success=True,
                data={'stock': stock, 'created': created}
            )

        except Category.DoesNotExist:
            logger.error(f"Category with id {category.id} does not exist.")
            return StockServiceResponse(
                success=False,
                error=f"The category with ID {category.id} does not exist."
            )
        except Exception as e:
            logger.error(f"Unexpected error in update_stock: {str(e)}")
            return StockServiceResponse(
                success=False,
                error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def validate_product(product) -> StockServiceResponse:
        """
        Validate the product and retrieve its details.
        """
        product_response = ProductService.get_product_by_id(product.id)
        if not product_response.success:
            return StockServiceResponse(success=False, error=product_response.error)
        return StockServiceResponse(success=True, data=product_response.data)

    @staticmethod
    def handle_exit_movement(product, quantity) -> StockServiceResponse:
        """
        Check if there is enough stock for an exit movement and notify managers if not.
        """
        current_stock_response = StockService.get_stock_quantity(product.id)
        if not current_stock_response.success:
            return current_stock_response

        current_stock = current_stock_response.data.get('quantity')

        if quantity > current_stock:
            message = (
                f"Critical stock for {product.name}. "
                f"Available: {current_stock}"
            )
            StockService.send_notification(
                product=product,
                notification_type='CRITICAL_STOCK',
                message=message,
            )

            return StockServiceResponse(
                success=False,
                error=f"Not enough stock for this exit movement. "
                      f"Available: {current_stock}, Required: {quantity}"
            )
        return StockServiceResponse(success=True)

    @staticmethod
    def update_stock_quantity(product, quantity, movement_type) -> StockServiceResponse:
        """
        Update the stock quantity based on the movement type.
        """
        if movement_type == 'EXIT':
            return StockService.update_stock(product, -quantity)
        elif movement_type == 'ENTRY':
            return StockService.update_stock(product, quantity)
        else:
            return StockServiceResponse(
                success=False,
                error='Invalid movement type.'
            )

    @staticmethod
    def create_stock_movement(
            product, quantity, movement_type, user, reason
    ) -> StockServiceResponse:
        """
        Create a stock movement record.
        """
        try:
            stock_movement = StockMovement.objects.create(
                movement_type=movement_type,
                quantity=quantity,
                reason=reason,
                user=user,
                product=product,
                category=product.category,
                subcategory=product.subcategory,
            )
            return StockServiceResponse(success=True, data=stock_movement)
        except Exception as e:
            return StockServiceResponse(
                success=False,
                error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def send_notification(product, notification_type, message) -> StockServiceResponse:
        """
        Send a notification to managers and storekeepers.
        """
        try:
            notif = notif_service.create_notification(
                product=product,
                notification_type=notification_type,
                message=message,
            )
            return StockServiceResponse(success=True, data=notif)
        except Exception as e:
            return StockServiceResponse(
                success=False,
                error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def send_low_stock_notification(product) -> StockServiceResponse:
        """
        Send a notification if the stock is below the minimum quantity.
        """
        current_stock_response = StockService.get_stock_quantity(product.id)
        if not current_stock_response.success:
            return current_stock_response

        current_stock = current_stock_response.data.get('quantity')

        if product.min_quantity > current_stock > 0:
            message = (
                f"Warning: Low stock for {product.name}. "
                f"Only {current_stock} left!"
            )
            StockService.send_notification(
                product=product,
                notification_type='LOW_STOCK',
                message=message,
            )
        return StockServiceResponse(success=True)

    @staticmethod
    def process_stock_movement(
            product, quantity, movement_type, user, reason=None
    ) -> StockServiceResponse:
        try:
            product = StockService.validate_product(product)
            if not product.success:
                return product

            if movement_type == 'EXIT':
                exit_response = StockService.handle_exit_movement(
                    product.data, quantity
                )
                if not exit_response.success:
                    return exit_response

            update_response = StockService.update_stock_quantity(
                product.data, quantity, movement_type
            )
            if not update_response.success:
                return update_response

            movement_response = StockService.create_stock_movement(
                product.data, quantity, movement_type, user, reason
            )
            if not movement_response.success:
                return movement_response

            if movement_type != 'EXIT':
                StockService.send_low_stock_notification(product.data)

            return StockServiceResponse(
                success=True,
                data={
                    'message': 'Stock movement processed successfully.',
                    'product': product.data,
                    'movement_type': movement_type,
                    'quantity': quantity,
                    'reason': reason
                }
            )

        except ValidationError as ve:
            logger.error(f"Validation error in process_stock_movement: {str(ve)}")
            return StockServiceResponse(
                success=False,
                error=str(ve)
            )
        except Exception as e:
            logger.error(f"Unexpected error in process_stock_movement: {str(e)}")
            return StockServiceResponse(
                success=False,
                error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_product_stock_details(product_id) -> StockServiceResponse:
        """
        Get the stock details (quantity) of a product in all categories and subcategories.
        """
        try:
            stock_details = Stock.objects.filter(product_id=product_id)
            logger.info(
                f"Retrieved stock details for {product_id}: {stock_details.count()} entries."
            )
            data = {
                'expired_products': stock_details,
                'count': stock_details.count(),
            }
            return StockServiceResponse(success=True, data=data)
        except Exception as e:
            logger.error(f"Error in get_product_stock_details: {str(e)}")
            return StockServiceResponse(
                success=False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def check_critical_stock_levels() -> StockServiceResponse:
        """
        Check all products for critical stock levels and return alerts.
        """
        try:
            critical_stocks = []

            stocks = Stock.objects.select_related('product').all()
            for stock in stocks:
                if stock.product.quantity < stock.product.min_quantity:
                    critical_stocks.append(
                        {
                            'product': stock.product.name,
                            'category': stock.category.name,
                            'subcategory': stock.subcategory.name,
                            'quantity': stock.product.quantity,
                            'min_quantity': stock.product.min_quantity,
                        }
                    )

                    message = (
                        f"Critical stock for {stock.product.name}. "
                        f"Available : {stock.product.quantity}"
                    )
                    StockService.send_notification(
                        product=stock.product,
                        notification_type='CRITICAL_STOCK',
                        message=message,
                    )

            logger.info(
                f"Checked critical stock levels."
                f" Found {len(critical_stocks)} critical stock items."
            )
            return StockServiceResponse(
                success=True,
                data=critical_stocks
            )
        except Exception as e:
            logger.error(f"Error in check_critical_stock_levels: {str(e)}")
            return StockServiceResponse(
                success=False,
                error=f"An unexpected error occurred: {str(e)}"
            )
