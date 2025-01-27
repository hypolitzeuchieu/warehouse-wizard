import logging
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from stock.models import Product, Stock, StockMovement, Category, SubCategory

logger = logging.getLogger(__name__)


class StockService:
    """
    Service for handling stock-related operations.
    """

    @staticmethod
    def create_or_update_product(
            name,
            description,
            unit_price,
            category_id,
            subcategory_id,
            expired_date,
            quantity,
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
                subcategory = SubCategory.objects.filter(id=subcategory_id).first()

            if expired_date and expired_date.date() < date.today():
                raise ValidationError({
                    "expired_date": f"The product cannot be created or updated because "
                                    f"it has already expired (expiry date: {expired_date.date()})."
                })

            with transaction.atomic():
                product, created = Product.objects.get_or_create(
                    name=name,
                    category=category,
                    subcategory=subcategory,
                    defaults={
                        'description': description,
                        'unit_price': unit_price,
                        'expiry_date': expired_date,
                        'quantity': quantity,
                        'min_quantity': min_quantity,
                        'on_promotion': on_promotion,
                        'promo_price': promo_price,
                        'promotion_start_date': promotion_start_date,
                        'promotion_end_date': promotion_end_date,
                        'is_expired': False,
                    }
                )

                if not created:
                    product.description = description
                    product.unit_price = unit_price
                    product.expiry_date = expired_date
                    product.quantity = quantity
                    product.min_quantity = min_quantity
                    product.on_promotion = on_promotion
                    product.promo_price = promo_price
                    product.promotion_start_date = promotion_start_date
                    product.promotion_end_date = promotion_end_date
                    product.is_expired = False
                    product.save()

                logger.info(f"Product {'created' if created else 'updated'}: {product.name}")
                StockService.update_stock(product, category, subcategory, quantity)
                return product, created

        except Category.DoesNotExist:
            logger.error(f"Category with ID {category_id} does not exist.")
            raise ValidationError(f"Category with ID {category_id} does not exist.")
        except ValidationError as ve:
            logger.error(f"Validation error: {ve}")
            raise ve
        except Exception as e:
            logger.error(f"Error in create_or_update_product: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})

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
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})

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
            raise ValidationError(f"subcategory with id {subcategory_id} not found.")
        except Exception as e:
            logger.error(f"Error in get_products_by_subcategory: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})

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
                product_id=product_id, category=category, subcategory=subcategory
            )

            if stock.quantity == 0:
                logger.info(
                    f"Product ID {product_id} is out of stock in category ID {category_id},"
                    f" subcategory ID {subcategory_id}"
                )
                return {
                    "status": "success",
                    "quantity": 0,
                    "message": "Product is out of stock."
                }

            logger.info(
                f"Stock quantity for product {stock.product.name} is {stock.quantity}"
            )
            return {
                "status": "success",
                "quantity": stock.quantity,
                "message": "Stock retrieved successfully."
            }
        except Stock.DoesNotExist:
            logger.warning(
                f"No stock record found for product ID {product_id},"
                f" category ID {category_id}, subcategory ID {subcategory_id}"
            )
            return {
                "status": "error",
                "message": "Stock record not found for the given product and category."
            }

        except Exception as e:
            logger.error(f"Error in get_stock_quantity: {str(e)}")
            return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}

    @staticmethod
    def update_stock(product, category, subcategory, quantity):
        """
        Update or create stock for a product in a specific category and subcategory.
        """
        try:
            if subcategory:
                subcategory = SubCategory.objects.select_related('category').get(id=subcategory.id)
                category = subcategory.category

            else:
                subcategory = None
                category = Category.objects.get(id=category.id)
            stock, created = Stock.objects.get_or_create(
                product=product,
                category=category,
                subcategory=subcategory,
                defaults={
                    'quantity': quantity
                }
            )
            if stock.quantity + quantity < 0:
                logger.warning(
                    f"Insufficient stock for product {product.name}, category {category.name}, "
                    f"subcategory {subcategory.name if subcategory else 'None'}. "
                    f"Current quantity: {stock.quantity}, Attempted adjustment: {quantity}."
                )
                raise ValidationError(
                    f"Insufficient stock for this operation. "
                    f"Current quantity: {stock.quantity}."
                )

            stock.quantity += quantity
            stock.save()

            if created:
                logger.info(
                    f"New stock created for product {product.name}, "
                    f"category {category.name}, "
                    f"subcategory {subcategory.name if subcategory else 'None'}. "
                    f"Initial quantity: {stock.quantity}."
                )
            else:
                logger.info(
                    f"Stock updated for product {product.name}, "
                    f"category {category.name}, "
                    f"subcategory {subcategory.name if subcategory else 'None'}. "
                    f"New quantity: {stock.quantity}."
                )

            return stock, created

        except Category.DoesNotExist:
            logger.error(f"Category with id {category.id} does not exist.")
            raise ValidationError(f"The category with ID {category.id} does not exist.")
        except Exception as e:
            logger.error(f"Unexpected error in update_stock: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})

    @staticmethod
    def process_stock_movement(
            product, category, subcategory, movement_type, quantity, user, reason=None
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
                    product.id, category.id, subcategory.id if subcategory else None
                ).get('quantity')
                if quantity > current_stock:
                    raise ValidationError(
                        f"Not enough stock for this exit movement. "
                        f"Available: {current_stock}, Required: {quantity}"
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
                    StockService.update_stock(product, category, subcategory, quantity)
                elif movement_type == 'EXIT':
                    StockService.update_stock(product, category, subcategory, -quantity)
            return {
                "product": product,
                "category": category,
                "subcategory": subcategory if subcategory else None,
                "movement_type": movement_type,
                "quantity": quantity,
                "reason": reason,
            }, 200

        except Product.DoesNotExist:
            raise ValidationError("Invalid product ID.")
        except Category.DoesNotExist:
            raise ValidationError("Invalid category ID.")
        except ValidationError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise ve
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise ValidationError({f"An unexpected error occurred: {str(e)}"})

    @staticmethod
    def get_all_stock():
        """
        Get a list of all stock entries (product + category + subcategory + quantity).
        """
        try:
            stocks = Stock.objects.select_related('category', 'subcategory').all()
            logger.info(f"Retrieved {stocks.count()} stock entries.")
            return stocks
        except Exception as e:
            logger.error(f"Error in get_all_stock: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})

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
            return {'expired_products': stock_details, 'count': stock_details.count()}
        except Exception as e:
            logger.error(f"Error in get_product_stock_details: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})

    @staticmethod
    def check_critical_stock_levels():
        """
        Check all products for critical stock levels and return alerts.
        """
        try:
            critical_stocks = []
            stocks = Stock.objects.select_related('product').all()
            for stock in stocks:
                if stock.quantity < stock.product.min_quantity:
                    critical_stocks.append({
                        'product': stock.product.name,
                        'category': stock.category.name,
                        'subcategory': stock.subcategory.name,
                        'quantity': stock.quantity,
                        'min_quantity': stock.product.min_quantity,
                    })
            logger.info(
                f"Checked critical stock levels."
                f" Found {len(critical_stocks)} critical stock items."
            )
            return critical_stocks
        except Exception as e:
            logger.error(f"Error in check_critical_stock_levels: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})

    @staticmethod
    def get_products_by_expiry_date():
        """
        Get all products that are expired or close to expiry.
        """
        try:
            expired_products = Product.objects.filter(
                expiry_date__lt=timezone.now(), is_expired=False
            )
            expired_products.update(is_expired=True)
            logger.info(f"Retrieved {expired_products.count()} expired products.")
            return {'expired_products': expired_products, 'count': expired_products.count()}
        except Exception as e:
            logger.error(f"Error in get_products_by_expiry_date: {str(e)}")
            raise ValidationError({"error": f"An unexpected error occurred: {str(e)}"})
