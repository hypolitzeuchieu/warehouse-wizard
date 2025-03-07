from __future__ import annotations

import logging
from datetime import date
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from notifications.service import NotificationService
from reports.service import ReportService
from rest_framework.exceptions import ValidationError
from stock.models import Category
from stock.models import Product
from stock.models import Stock
from stock.models import StockMovement
from stock.models import SubCategory
from utils.s3_storage import upload_file_to_s3

logger = logging.getLogger(__name__)

reports_service = ReportService()
notif_service = NotificationService()


class StockService:
    """
    Service for handling stock-related operations.
    """

    @staticmethod
    def get_products_by_category(category_id):
        """
        Get all products in a specific category.
        """
        try:
            category = Category.objects.get(id=category_id)
            products = Product.objects.filter(category=category)
            logger.info(
                f"Retrieved {products.count()} products for category: {category.name}"
            )
            return products
        except Category.DoesNotExist:
            logger.error(f"Category with id {category_id} not found.")
            raise ValidationError(f"Category with id {category_id} not found.")
        except Exception as e:
            logger.error(f"Error in get_products_by_category: {str(e)}")
            raise ValidationError(
                {'error': f"An unexpected error occurred: {str(e)}"}
            )

    @staticmethod
    def get_products_by_subcategory(subcategory_id):
        """
        Get all products in a specific category.
        """
        try:
            subcategory = SubCategory.objects.get(id=subcategory_id)
            products = Product.objects.filter(subcategory=subcategory)
            logger.info(
                f"Retrieved {products.count()} products for category: {subcategory_id}"
            )
            return products
        except SubCategory.DoesNotExist:
            logger.error(f"subcategory with id {subcategory_id} not found.")
            raise ValidationError(
                f"subcategory with id {subcategory_id} not found."
            )
        except Exception as e:
            logger.error(f"Error in get_products_by_subcategory: {str(e)}")
            raise ValidationError(
                {'error': f"An unexpected error occurred: {str(e)}"}
            )

    @staticmethod
    def get_stock_quantity(product_id):
        """
        Get the current stock quantity of a product in a specific category and subcategory.
        """
        try:
            product_response = ProductService.get_product_by_id(product_id)
            if not product_response.success:
                raise ValidationError(product_response.error)

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
                return {
                    'status': 'success',
                    'quantity': 0,
                    'message': 'Product is out of stock.',
                }

            logger.info(
                f"Stock quantity for product {stock.product.name} is {stock.product.quantity}"
            )
            return {
                'status': 'success',
                'quantity': stock.product.quantity,
                'message': 'Stock retrieved successfully.',
            }
        except Stock.DoesNotExist:
            logger.warning(
                f"No stock record found for product ID {product_id},"
                f" category ID {category}, subcategory ID {subcategory}"
            )
            return {
                'status': 'error',
                'message': 'Stock record not found for the given product and category.',
            }

        except Exception as e:
            logger.error(f"Error in get_stock_quantity: {str(e)}")
            return {
                'status': 'error',
                'message': f"An unexpected error occurred: {str(e)}",
            }

    @staticmethod
    def update_stock(product, quantity):
        """
        Update or create stock for a product in a specific category and subcategory.
        """
        try:
            product_response = ProductService.get_product_by_id(product.id)
            if not product_response.success:
                raise ValidationError(product_response.error)

            product = product_response.data
            category = product.category
            subcategory = product.subcategory

            stock, created = Stock.objects.get_or_create(
                product=product,
                category=category,
                subcategory=subcategory,
            )
            if stock.product.quantity + quantity < 0:
                logger.warning(
                    f"Insufficient stock for product {product.name}, category {category.name},"
                    f"subcategory {subcategory.name if subcategory else 'None'}. "
                    f"Current quantity: {stock.quantity}, Attempted adjustment: {quantity}."
                )
                raise ValidationError(
                    f"Insufficient stock for this operation. "
                    f"Current quantity: {stock.quantity}."
                )
            product.quantity += quantity
            product.save()

            return stock, created

        except Category.DoesNotExist:
            logger.error(f"Category with id {category.id} does not exist.")
            raise ValidationError(
                f"The category with ID {category.id} does not exist."
            )
        except Exception as e:
            logger.error(f"Unexpected error in update_stock: {str(e)}")
            raise ValidationError(
                {'error': f"An unexpected error occurred: {str(e)}"}
            )

    @staticmethod
    def validate_product(product):
        """
        Validate the product and retrieve its details.
        """
        product_response = ProductService.get_product_by_id(product.id)
        if not product_response.success:
            raise ValidationError(product_response.error)
        return product_response.data

    @staticmethod
    def handle_exit_movement(product, quantity):
        """
        Check if there is enough stock for an exit movement and notify managers if not.
        """
        current_stock = StockService.get_stock_quantity(product.id).get('quantity')

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

            raise ValidationError(
                f"Not enough stock for this exit movement. "
                f"Available: {current_stock}, Required: {quantity}"
            )

    @staticmethod
    def update_stock_quantity(product, quantity, movement_type):
        """
        Update the stock quantity based on the movement type.
        """
        if movement_type == 'EXIT':
            StockService.update_stock(product, -quantity)
        elif movement_type == 'ENTRY':
            StockService.update_stock(product, quantity)
        # elif movement_type == "ADJUSTMENT":
        #     StockService.set_stock(product, quantity)
        else:
            raise ValidationError('Invalid movement type.')

    @staticmethod
    def create_stock_movement(product, quantity, movement_type, user, reason):
        """
        Create a stock movement record.
        """
        return StockMovement.objects.create(
            movement_type=movement_type,
            quantity=quantity,
            reason=reason,
            user=user,
            product=product,
            category=product.category,
            subcategory=product.subcategory,
        )

    @staticmethod
    def send_notification(product, notification_type, message):
        """
        Send a notification to managers and storekeepers.
        """
        users = reports_service.get_managers_and_store_keepers()
        if users.success:
            for manager in users.data:
                notif_service.create_notification(
                    user=manager,
                    product=product,
                    notification_type=notification_type,
                    message=message,
                )
        else:
            logger.warning('No managers found to notify about stock levels.')

    @staticmethod
    def send_low_stock_notification(product):
        """
        Send a notification if the stock is below the minimum quantity.
        """
        current_stock = StockService.get_stock_quantity(product.id).get('quantity')
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

    @staticmethod
    def process_stock_movement(product, quantity, movement_type, user, reason=None):
        """
        Process a stock movement: add, remove, or adjust quantity based on movement_type.
        """
        try:
            product = StockService.validate_product(product)

            with transaction.atomic():
                if movement_type == 'EXIT':
                    StockService.handle_exit_movement(product, quantity)

                StockService.update_stock_quantity(product, quantity, movement_type)
                StockService.create_stock_movement(
                    product, quantity, movement_type, user, reason
                )
                if movement_type != 'EXIT':
                    StockService.send_low_stock_notification(product)

            return {
                'status': 'success',
                'message': 'Stock movement processed successfully.',
                'product': product,
                'movement_type': movement_type,
                'quantity': quantity,
                'reason': reason
            }, 200

        except ValidationError as ve:
            logger.error(f"Validation error in process_stock_movement: {str(ve)}")
            raise ve
        except Exception as e:
            logger.error(f"Unexpected error in process_stock_movement: {str(e)}")
            raise ValidationError({'error': f"An unexpected error occurred: {str(e)}"})

    @staticmethod
    def get_product_stock_details(product_id):
        """
        Get the stock details (quantity) of a product in all categories and subcategories.
        """
        try:
            stock_details = Stock.objects.filter(product_id=product_id)
            logger.info(
                f"Retrieved stock details for {product_id}: {stock_details.count()} entries."
            )
            return {
                'expired_products': stock_details,
                'count': stock_details.count(),
            }
        except Exception as e:
            logger.error(f"Error in get_product_stock_details: {str(e)}")
            raise ValidationError(
                {'error': f"An unexpected error occurred: {str(e)}"}
            )

    @staticmethod
    def check_critical_stock_levels():
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
            return critical_stocks
        except Exception as e:
            logger.error(f"Error in check_critical_stock_levels: {str(e)}")
            raise ValidationError(
                {'error': f"An unexpected error occurred: {str(e)}"}
            )


class ServiceProductResponse:
    def __init__(self, success, data=None, error=None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self):
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error
        }


class ProductService:
    """
        Service for handling Product operations.
    """
    @staticmethod
    def create_product(
            name,
            description,
            unit_price,
            category_id,
            subcategory_id,
            expired_date,
            quantity,
            image=None,
            on_promotion=False,
            promo_price=None,
            promotion_start_date=None,
            promotion_end_date=None,
            min_quantity=0,
    ):
        """
        Create a product or increment its stock if it already exists.
        """
        try:
            category = Category.objects.get(id=category_id)
            subcategory = None
            if subcategory_id:
                subcategory = SubCategory.objects.filter(
                    id=subcategory_id
                ).first()

            if expired_date and expired_date.date() < date.today():
                return ServiceProductResponse(
                    False,
                    {'expired_date': f"The product cannot be created it has "
                                     f"already expired (expiry date: {expired_date.date()})."
                     }
                )
            image_url = upload_file_to_s3(image) if image else None

            with transaction.atomic():
                product, created = Product.objects.get_or_create(
                    name=name,
                    category=category,
                    subcategory=subcategory,
                    defaults={
                        'description': description,
                        'unit_price': unit_price,
                        'expiry_date': expired_date,
                        'quantity': 0,
                        'image': image_url,
                        'min_quantity': min_quantity,
                        'on_promotion': on_promotion,
                        'promo_price': promo_price,
                        'promotion_start_date': promotion_start_date,
                        'promotion_end_date': promotion_end_date,
                        'is_expired': False,
                    },
                )

                StockService.update_stock(
                    product, category, subcategory, quantity
                )
                return ServiceProductResponse(True, data=product)

        except Category.DoesNotExist:
            return ServiceProductResponse(
                False,
                error=f"Category with ID {category_id} does not exist."
            )
        except Exception as e:
            return ServiceProductResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def update_product(product_id, data):
        try:
            product = Product.objects.get(id=product_id)
            for key, value in data.items():
                setattr(product, key, value)
            product.save()
            logger.info(f"Product updated: {product.name}")
            return ServiceProductResponse(True, data=product)

        except Product.DoesNotExist:
            return ServiceProductResponse(
                False, error=f"Product with ID {product_id} not found."
            )
        except Exception as e:
            return ServiceProductResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def delete_product(product_id):
        try:
            product = Product.objects.get(id=product_id)
            product.delete()
            logger.info(f"Product deleted: {product.name}")
            return ServiceProductResponse(True, data='Product deleted successfully')

        except Product.DoesNotExist:
            return ServiceProductResponse(
                False, error=f"Product with ID {product_id} not found."
            )
        except Exception as e:
            return ServiceProductResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_product_by_id(product_id: str):
        """
        Get a product by its ID.
        """
        try:
            product = Product.objects.get(id=product_id)
            logger.info(f"Retrieved product: {product.name}")
            return ServiceProductResponse(True, data=product)
        except Product.DoesNotExist:
            logger.error(f"Product with ID {product_id} not found.")
            return ServiceProductResponse(
                False, error=f"Product with ID {product_id} not found."
            )
        except Exception as e:
            logger.error(f"Error in get_product_by_id: {str(e)}")
            ServiceProductResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_all_stock():
        """
        Get a list of all stock entries (product + category + subcategory + quantity).
        """
        try:
            stocks = Stock.objects.select_related(
                'category', 'subcategory'
            ).all()
            logger.info(f"Retrieved {stocks.count()} stock entries.")
            return ServiceProductResponse(success=True, data=stocks)
        except Exception as e:
            logger.error(f"Error in get_all_stock: {str(e)}")
            return ServiceProductResponse(
                False,
                error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_products_by_expiry_date():
        """
        Get all products that are expired or close to expiry.
        """
        try:
            now = timezone.now()
            soon = now + timedelta(days=14)

            expired_products = Product.objects.filter(
                expiry_date__lt=now
            ).select_related('category', 'subcategory')
            expired_products.update(
                is_expired=True, expiry_date=F('expiry_date')
            )
            users = ReportService.get_managers_and_store_keepers()
            for product in expired_products:
                message = (
                    f"The product {product.name} is expired. "
                    f"Expired date : {product.expiry_date}"
                )
                if users.success:
                    for manager in users.data:
                        notif_service.create_notification(
                            user=manager,
                            product=product,
                            notification_type='EXPIRED',
                            message=message,
                        )
                else:
                    logger.warning(
                        'No managers found to notify about critical stock levels.'
                    )

            near_expiry = Product.objects.filter(
                expiry_date__range=(now, soon), is_expired=False
            ).select_related('category', 'subcategory')
            for product in near_expiry:
                message = (
                    f"The product {product.name} is near to expired."
                    f" Expired date : {product.expiry_date}"
                )
                if users.success:
                    for manager in users.data:
                        notif_service.create_notification(
                            user=manager,
                            product=product,
                            notification_type='NEAR_EXPIRY',
                            message=message,
                        )
            logger.info(
                f"Retrieved {expired_products.count()} expired products."
            )
            return ServiceProductResponse(
                True,
                {'expired_products': expired_products,
                 'count': expired_products.count(),
                 'near_expiry': near_expiry,
                 'near_expiry_count': near_expiry.count()
                 }
            )
        except Exception as e:
            logger.error(f"Error in get_products_by_expiry_date: {str(e)}")
            return ServiceProductResponse(
                False,
                error=f"An unexpected error occurred: {str(e)}"
            )
