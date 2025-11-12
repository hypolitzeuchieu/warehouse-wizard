from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.stock.models import Product
from utils.barcode_generator import BarcodeService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate barcodes for products without one"

    def handle(self, *args, **kwargs):
        products = Product.objects.filter(barcode__isnull=True)
        total = products.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("All products already have barcodes!"))
            return

        self.stdout.write(f"Generating barcodes for {total} products...")

        for i, product in enumerate(products, 1):
            try:
                barcode_value = BarcodeService.generate_ean13_barcode()
                barcode_url = BarcodeService.create_and_upload_barcode_image(
                    barcode_value, filename=f"product_{product.id}"
                )
                product.barcode = barcode_value
                product.barcode_image_url = barcode_url
                product.save()

                self.stdout.write(
                    self.style.SUCCESS(f"[{i}/{total}] Generated barcode for {product.name}")
                )
                logger.info(f"Generated barcode for product {product.id}: {barcode_value}")

            except Exception as e:
                logger.error(f"Error generating barcode for product {product.id}: {e}")
                self.stdout.write(self.style.ERROR(f"[{i}/{total}] Failed for {product.name}: {e}"))

        self.stdout.write(self.style.SUCCESS("Barcode generation completed!"))
