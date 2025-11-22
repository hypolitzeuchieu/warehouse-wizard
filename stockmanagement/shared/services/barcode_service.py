"""Barcode service for product barcode generation and management."""

from __future__ import annotations

import io
import logging
import random

from barcode import EAN13
from barcode.writer import ImageWriter

from shared.services.s3_service import S3Service

logger = logging.getLogger(__name__)


class BarcodeService:
    """Service for generating and managing barcodes."""

    def __init__(self, s3_service: S3Service | None = None) -> None:
        """Initialize barcode service."""
        self.s3_service = s3_service or S3Service()

    def generate_ean13_barcode(self) -> str:
        """
        Generate a random EAN-13 barcode value.

        Returns:
            EAN-13 barcode string (13 digits)
        """
        try:
            first_digit = random.randint(1, 9)
            remaining_digits = [random.randint(0, 9) for _ in range(11)]
            digits = [first_digit] + remaining_digits

            weighted_sum = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
            checksum = (10 - (weighted_sum % 10)) % 10

            base = "".join(str(d) for d in digits)
            barcode_value = base + str(checksum)

            logger.info(f"Generated EAN-13 barcode: {barcode_value}")
            return barcode_value

        except Exception as e:
            logger.error(f"Error generating barcode: {str(e)}")
            raise

    def create_barcode_image(self, barcode_value: str) -> io.BytesIO:
        """
        Create a barcode image.

        Args:
            barcode_value: EAN-13 barcode value

        Returns:
            Barcode image as BytesIO
        """
        try:
            buffer = io.BytesIO()
            ean = EAN13(barcode_value, writer=ImageWriter())
            ean.write(buffer)
            buffer.seek(0)

            # Set content type for S3 upload
            buffer.content_type = "image/png"

            logger.info(f"Barcode image created for: {barcode_value}")
            return buffer

        except Exception as e:
            logger.error(f"Error creating barcode image: {str(e)}")
            raise

    def generate_and_upload_barcode(
        self,
        barcode_value: str | None = None,
        product_repository=None,
    ) -> tuple[str, str]:
        """
        Generate barcode value and upload barcode image to S3.

        Args:
            barcode_value: Optional barcode value. If not provided, generates a new one.
            product_repository: Optional ProductRepository to check for uniqueness.

        Returns:
            Tuple of (barcode_value, barcode_image_url)
        """
        try:
            max_attempts = 10
            attempts = 0

            # Generate unique barcode value
            while attempts < max_attempts:
                if not barcode_value:
                    barcode_value = self.generate_ean13_barcode()

                # Check uniqueness if repository is provided
                if product_repository:
                    if not product_repository.barcode_exists_globally(barcode_value):
                        break
                    # Barcode exists, generate a new one
                    barcode_value = None
                else:
                    # No repository provided, use generated barcode
                    break

                attempts += 1

            if attempts >= max_attempts:
                raise Exception("Failed to generate unique barcode after 10 attempts")

            # Create barcode image
            barcode_image = self.create_barcode_image(barcode_value)

            # Upload to S3
            barcode_url = self.s3_service.upload_barcode_image(
                barcode_image=barcode_image,
                barcode_value=barcode_value,
            )

            logger.info(f"Barcode generated and uploaded: {barcode_value} -> {barcode_url}")
            return barcode_value, barcode_url

        except Exception as e:
            logger.error(f"Error generating and uploading barcode: {str(e)}")
            raise
