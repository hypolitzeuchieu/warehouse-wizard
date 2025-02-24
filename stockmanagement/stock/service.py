from __future__ import annotations

import logging
import os
import uuid
from datetime import date
from datetime import timedelta

import boto3
from botocore.exceptions import ClientError
from botocore.exceptions import NoCredentialsError
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

logger = logging.getLogger(__name__)


class StockService:
    """
    Service for handling stock-related operations.
    """

    reports_service = ReportService()
    notif_service = NotificationService()

    @staticmethod
    def validate_image_format(file):
        """
        Validate the uploaded file format.

        :param file: File object to validate
        :raises ValidationError: If the file format is not allowed
        :return: The valid file extension
        """
        allowed_image_formats = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
        }

        file_type = file.content_type
        if file_type not in allowed_image_formats:
            raise ValidationError({
                'error': f"Invalid file format: {file_type}."
                         f" Allowed formats: {list(allowed_image_formats.keys())}"
            })
        return allowed_image_formats[file_type]

    @staticmethod
    def upload_file_to_s3(file):
        """
        Upload an image to S3 after validating its format.

        :param file: File object to upload
        :return: Public URL of the uploaded image
        """
        if not file:
            return None

        # Vérifier le format de l'image
        file_extension = StockService.validate_image_format(file)

        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION_NAME'),
        )

        try:
            # Générer un nom unique
            file_name = f"products/{uuid.uuid4()}{file_extension}"

            # Upload du fichier avec permissions publiques
            s3_client.upload_fileobj(
                file.file,
                os.getenv('AWS_BUCKET_NAME'),
                file_name,
                ExtraArgs={'ContentType': file.content_type, 'ACL': 'public-read'}
            )
            image_url = (f"https://{os.getenv('AWS_BUCKET_NAME')}.s3."
                         f"{os.getenv('AWS_REGION_NAME')}.amazonaws.com/{file_name}")
            return image_url

        except NoCredentialsError:
            logger.error('AWS credentials are missing.')
            raise ValidationError({'error': 'AWS credentials are missing.'})
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise ValidationError({'error': f"S3 upload failed: {e}"})
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            raise ValidationError(f"Unexpected error occurred: {str(e)}")

    @staticmethod
    def create_or_update_product(
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
                raise ValidationError(
                    {
                        'expired_date': f"The product cannot be created or updated because "
                        f"it has already expired (expiry date: {expired_date.date()})."
                    }
                )
            image_url = StockService.upload_file_to_s3(image) if image else None

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
                return product, created

        except Category.DoesNotExist:
            logger.error(f"Category with ID {category_id} does not exist.")
            raise ValidationError(
                f"Category with ID {category_id} does not exist."
            )
        except ValidationError as ve:
            logger.error(f"Validation error: {ve}")
            raise ve
        except Exception as e:
            logger.error(f"Error in create_or_update_product: {str(e)}")
            raise ValidationError(
                {'error': f"An unexpected error occurred: {str(e)}"}
            )

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
    def get_stock_quantity(product_id, category_id, subcategory_id):
        """
        Get the current stock quantity of a product in a specific category and subcategory.
        """
        try:
            if subcategory_id:
                subcategory = SubCategory.objects.get(id=subcategory_id)
                category = subcategory.category
            else:
                subcategory = None
                category = Category.objects.get(id=category_id)

            stock = Stock.objects.get(
                product_id=product_id,
                category=category,
                subcategory=subcategory,
            )

            if stock.product.quantity == 0:
                logger.info(
                    f"Product ID {product_id} is out of stock in category ID {category_id},"
                    f" subcategory ID {subcategory_id}"
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
                f" category ID {category_id}, subcategory ID {subcategory_id}"
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
    def update_stock(product, category, subcategory, quantity):
        """
        Update or create stock for a product in a specific category and subcategory.
        """
        try:
            if subcategory:
                subcategory = SubCategory.objects.select_related(
                    'category'
                ).get(id=subcategory.id)
                category = subcategory.category

            else:
                subcategory = None
                category = Category.objects.get(id=category.id)
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

            if created:
                logger.info(
                    f"New stock created for product {product.name}, "
                    f"category {category.name}, "
                    f"subcategory {subcategory.name if subcategory else None}. "
                    f"Initial quantity: {stock.product.quantity}."
                )
            else:
                logger.info(
                    f"Stock updated for product {product.name}, "
                    f"category {category.name}, "
                    f"subcategory {subcategory.name if subcategory else None}. "
                    f"New quantity: {stock.product.quantity}."
                )

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

    def process_stock_movement(
        self,
        product,
        category,
        subcategory,
        movement_type,
        quantity,
        user,
        reason=None,
    ):
        """
        Process a stock movement (entry or exit).
        """
        try:
            product = Product.objects.get(id=product.id)
            if subcategory:
                subcategory = SubCategory.objects.get(id=subcategory.id)
                category = subcategory.category
            else:
                category = Category.objects.get(id=category.id)

            if movement_type == 'EXIT':
                current_stock = StockService.get_stock_quantity(
                    product.id,
                    category.id,
                    subcategory.id if subcategory else None,
                ).get('quantity')
                if quantity > current_stock:
                    message = (
                        f"Critical stock for {product.name}. "
                        f"Available : {product.quantity}"
                    )
                    users = (
                        self.reports_service.get_managers_and_store_keepers()
                    )
                    if users.success:
                        for manager in users.data:
                            self.notif_service.create_notification(
                                user=manager,
                                product=product,
                                notification_type='CRITICAL_STOCK',
                                message=message,
                            )
                        raise ValidationError(
                            f"Not enough stock for this exit movement. "
                            f"Available: {current_stock}, Required: {quantity}"
                        )
                    else:
                        logger.warning(
                            'No managers found to notify about critical stock levels.'
                        )
            with transaction.atomic():
                StockMovement.objects.create(
                    product=product,
                    category=category,
                    subcategory=subcategory,
                    movement_type=movement_type,
                    quantity=quantity,
                    reason=reason,
                    user=user,
                )
                if movement_type == 'ENTRY':
                    StockService.update_stock(
                        product, category, subcategory, quantity
                    )
                elif movement_type == 'EXIT':
                    StockService.update_stock(
                        product, category, subcategory, -quantity
                    )
            return {
                'product': product,
                'category': category,
                'subcategory': subcategory if subcategory else None,
                'movement_type': movement_type,
                'quantity': quantity,
                'reason': reason,
            }, 200

        except Product.DoesNotExist:
            raise ValidationError('Invalid product ID.')
        except Category.DoesNotExist:
            raise ValidationError('Invalid category ID.')
        except ValidationError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise ve
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise ValidationError({f"An unexpected error occurred: {str(e)}"})

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

    def check_critical_stock_levels(self):
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
                    users = (
                        self.reports_service.get_managers_and_store_keepers()
                    )
                    if users.success:
                        for manager in users.data:
                            self.notif_service.create_notification(
                                user=manager,
                                product=stock.product,
                                notification_type='CRITICAL_STOCK',
                                message=message,
                            )
                    else:
                        logger.warning(
                            'No managers found to notify about critical stock levels.'
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

    def get_products_by_expiry_date(self):
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
                        self.notif_service.create_notification(
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
                for manager in users:
                    self.notif_service.create_notification(
                        user=manager,
                        product=product,
                        notification_type='NEAR_EXPIRY',
                        message=message,
                    )
            logger.info(
                f"Retrieved {expired_products.count()} expired products."
            )
            return {
                'expired_products': expired_products,
                'count': expired_products.count(),
                'near_expiry': near_expiry,
                'near_expiry_count': near_expiry.count(),
            }
        except Exception as e:
            logger.error(f"Error in get_products_by_expiry_date: {str(e)}")
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
            image_url = StockService.upload_file_to_s3(image) if image else None

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
    def get_product_detail(product_id: str):
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
            logger.error(f"Error in get_product_detail: {str(e)}")
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
