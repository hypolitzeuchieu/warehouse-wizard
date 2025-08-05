from __future__ import annotations

import io
import logging
import uuid

import boto3
from barcode import EAN13
from barcode.writer import ImageWriter
from django.conf import settings

logger = logging.getLogger(__name__)


class BarcodeService:
    """Service de génération et gestion de codes-barres"""

    @staticmethod
    def generate_ean13_barcode():
        """Generate a random EAN-13 barcode value"""
        try:
            base = str(uuid.uuid4().int)[:12].zfill(12)
            digits = [int(d) for d in base]
            weighted_sum = sum(d * (1 if i % 2 == 0 else 3)
                               for i, d in enumerate(digits))
            checksum = (10 - (weighted_sum % 10)) % 10
            return base + str(checksum)
        except Exception as e:
            logger.error(f"Error during generating barcode: {str(e)}")
            raise

    @staticmethod
    def create_and_upload_barcode_image(barcode_value, filename: str = None):
        try:
            buffer = io.BytesIO()
            ean = EAN13(barcode_value, writer=ImageWriter())
            ean.write(buffer)
            buffer.seek(0)

            file_name = f"barcodes/{filename or 'code'}_{barcode_value}.png"
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION_NAME
            )

            s3.upload_fileobj(
                buffer,
                settings.AWS_BUCKET_NAME,
                file_name,
                ExtraArgs={'ContentType': 'image/png'}
            )

            barcode_url = f"https://{settings.AWS_BUCKET_NAME}.s3.amazonaws.com/{file_name}"
            logger.info(f"Barcode image uploaded successfully: {barcode_url}")
            return barcode_url

        except Exception as e:
            logger.exception(f"Unexpected error while creating barcode image: {str(e)}")
            return None
