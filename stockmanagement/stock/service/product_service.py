from __future__ import annotations

import logging
from datetime import date
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from notifications.service import NotificationService
from reports.service.invoice_service import ReportService
from stock.models import Category
from stock.models import Product
from stock.models import Stock
from stock.models import SubCategory
from stock.service.entities import StockServiceResponse
from utils.s3_storage import upload_file_to_s3

logger = logging.getLogger(__name__)

reports_service = ReportService()
notif_service = NotificationService()


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
            image,
            purchase_price,
            on_promotion=False,
            promo_price=None,
            promotion_start_date=None,
            promotion_end_date=None,
            min_quantity=0,
    ) -> StockServiceResponse:
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
                return StockServiceResponse(
                    False,
                    {'expired_date': f"The product cannot be created it has "
                                     f"already expired (expiry date: {expired_date.date()})."
                     }
                )
            image_url = upload_file_to_s3(image) if image else None

            with (transaction.atomic()):
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
                        'purchase_price': purchase_price,
                        'min_quantity': min_quantity,
                        'on_promotion': on_promotion,
                        'promo_price': promo_price,
                        'promotion_start_date': promotion_start_date,
                        'promotion_end_date': promotion_end_date,
                        'is_expired': False,
                    },
                )
                if not created and image_url:
                    product.image = image_url
                    product.save(update_fields=['image'])
                logger.info(f"Product image found: {product.image}")
                logger.info(f"Product successfully created: {product.name}"
                            f" with ID: {product.id}") if created else None

                from stock.service.stock_service import StockService
                StockService.update_stock(
                    product, quantity
                )
                return StockServiceResponse(True, data=product)

        except Category.DoesNotExist:
            return StockServiceResponse(
                False,
                error=f"Category with ID {category_id} does not exist."
            )
        except Exception as e:
            return StockServiceResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def update_product(product_id, data) -> StockServiceResponse:
        try:
            product = Product.objects.get(id=product_id)
            image = data.get('image', None)
            if image:
                image_url = upload_file_to_s3(image)
                data['image'] = image_url
            for key, value in data.items():
                setattr(product, key, value)
            product.save()
            logger.info(f"Product updated: {product.name}")
            return StockServiceResponse(True, data=product)

        except Product.DoesNotExist:
            return StockServiceResponse(
                False, error=f"Product with ID {product_id} not found."
            )
        except Exception as e:
            return StockServiceResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def delete_product(product_id) -> StockServiceResponse:
        try:
            product = Product.objects.get(id=product_id)
            product.delete()
            logger.info(f"Product deleted: {product.name}")
            return StockServiceResponse(True, data='Product deleted successfully')

        except Product.DoesNotExist:
            return StockServiceResponse(
                False, error=f"Product with ID {product_id} not found."
            )
        except Exception as e:
            return StockServiceResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_product_by_id(product_id: str) -> StockServiceResponse:
        """
        Get a product by its ID.
        """
        try:
            product = Product.objects.get(id=product_id)
            logger.info(f"Retrieved product: {product.name}")
            return StockServiceResponse(True, data=product)
        except Product.DoesNotExist:
            logger.error(f"Product with ID {product_id} not found.")
            return StockServiceResponse(
                False, error=f"Product with ID {product_id} not found."
            )
        except Exception as e:
            logger.error(f"Error in get_product_by_id: {str(e)}")
            return StockServiceResponse(
                False, error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_all_stock() -> StockServiceResponse:
        """
        Get a list of all stock entries (product + category + subcategory + quantity).
        """
        try:
            stocks = Stock.objects.select_related(
                'product', 'category', 'subcategory'
            ).all()

            logger.info(f"Retrieved {stocks.count()} stock entries.")
            return StockServiceResponse(success=True, data=stocks)

        except Exception as e:
            logger.error(f"Error in get_all_stock: {str(e)}")
            return StockServiceResponse(
                False,
                error=f"An unexpected error occurred: {str(e)}"
            )

    @staticmethod
    def get_products_by_expiry_date() -> StockServiceResponse:
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
            for product in expired_products:
                message = (
                    f"The product {product.name} is expired. "
                    f"Expired date : {product.expiry_date}"
                )
                notif_service.create_notification(
                    product=product,
                    notification_type='EXPIRED',
                    message=message,
                )

            near_expiry = Product.objects.filter(
                expiry_date__range=(now, soon), is_expired=False
            ).select_related('category', 'subcategory')
            for product in near_expiry:
                message = (
                    f"The product {product.name} is near to expired."
                    f" Expired date : {product.expiry_date}"
                )
                notif_service.create_notification(
                    product=product,
                    notification_type='NEAR_EXPIRY',
                    message=message,
                )
            logger.info(
                f"Retrieved {expired_products.count()} expired products."
            )
            return StockServiceResponse(
                True,
                {'expired_products': expired_products,
                 'count': expired_products.count(),
                 'near_expiry': near_expiry,
                 'near_expiry_count': near_expiry.count()
                 }
            )
        except Exception as e:
            logger.error(f"Error in get_products_by_expiry_date: {str(e)}")
            return StockServiceResponse(
                False,
                error=f"An unexpected error occurred: {str(e)}"
            )
