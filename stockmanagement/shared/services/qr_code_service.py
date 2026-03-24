"""QR code service for business access."""

from __future__ import annotations

import io
import logging
from uuid import UUID

import qrcode

from shared.services.s3_service import S3Service

logger = logging.getLogger(__name__)


class QRCodeService:
    """Service for generating and managing QR codes."""

    def __init__(self, s3_service: S3Service | None = None) -> None:
        """Initialize QR code service."""
        self.s3_service = s3_service or S3Service()

    def generate_qr_code(
        self,
        data: str,
        size: int = 10,
        border: int = 4,
    ) -> io.BytesIO:
        """
        Generate a QR code image.

        Args:
            data: Data to encode in QR code
            size: Box size (default: 10)
            border: Border size (default: 4)

        Returns:
            QR code image as BytesIO
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=size,
                border=border,
            )
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            # Set content type for S3 upload
            buffer.content_type = "image/png"

            logger.info(f"QR code generated successfully for data: {data[:50]}...")
            return buffer

        except Exception as e:
            logger.error(f"Error generating QR code: {str(e)}")
            raise

    def generate_business_qr_code(
        self,
        business_id: UUID,
        base_url: str = "https://maahbusiness.com",
    ) -> tuple[str, io.BytesIO]:
        """
        Generate QR code for business access.

        Args:
            business_id: Business UUID
            base_url: Base URL for the platform

        Returns:
            Tuple of (QR code URL, QR code image BytesIO)
        """
        # Generate QR code data URL
        qr_data = f"{base_url}/api/v1/businesses/{business_id}/"

        # Generate QR code image
        qr_image = self.generate_qr_code(qr_data)

        return qr_data, qr_image

    def upload_business_qr_code(
        self,
        business_id: UUID,
        business_name: str | None = None,
        base_url: str = "https://maahbusiness.com",
    ) -> str:
        """
        Generate and upload QR code for business access to S3.

        Args:
            business_id: Business UUID
            base_url: Base URL for the platform

        Returns:
            Public URL of the uploaded QR code image
        """
        try:
            # Generate QR code
            qr_data, qr_image = self.generate_business_qr_code(business_id, base_url)

            filename = self.s3_service.build_named_filename(
                prefix="business-qr",
                name=business_name,
                entity_id=str(business_id),
            )
            qr_url = self.s3_service.upload_qr_code_image(qr_image=qr_image, filename=filename)

            logger.info(f"Business QR code uploaded to S3: {qr_url}")
            return qr_url

        except Exception as e:
            logger.error(f"Error uploading business QR code: {str(e)}")
            raise

    def scan_qr_code(self, qr_data: str) -> dict[str, str | UUID]:
        """
        Parse QR code data to extract business information.

        Args:
            qr_data: QR code data string

        Returns:
            Dictionary with business_id and other extracted data

        Raises:
            ValueError: If QR code data is invalid
        """
        try:

            business_id_str = None

            if "/businesses/" in qr_data:
                parts = qr_data.split("/businesses/")
                if len(parts) > 1:
                    business_id_str = parts[1].strip().rstrip("/").split("/")[0].strip()

            elif "/business/" in qr_data:
                parts = qr_data.split("/business/")
                if len(parts) > 1:
                    business_id_str = parts[1].strip().rstrip("/").split("/")[0].strip()

            if not business_id_str:
                raise ValueError(
                    "Invalid QR code format. Expected: .../businesses/{business_id}/ or .../business/{business_id}"
                )

            business_id = UUID(business_id_str)

            return {
                "business_id": business_id,
                "qr_data": qr_data,
            }

        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing QR code data: {str(e)}")
            raise ValueError(f"Invalid QR code data: {str(e)}") from e
