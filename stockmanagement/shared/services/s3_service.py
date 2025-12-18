"""S3 service for file uploads (images, barcodes, logos)."""

from __future__ import annotations

import logging
import re
import uuid
from io import BytesIO
from typing import BinaryIO
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings

from shared.exceptions.base import BaseAPIException

logger = logging.getLogger(__name__)


class S3Service:
    """Service for S3 file uploads."""

    # Allowed image formats
    ALLOWED_IMAGE_FORMATS = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }

    # Allowed file types
    ALLOWED_FILE_TYPES = {
        "image": ALLOWED_IMAGE_FORMATS,
        "barcode": {"image/png": ".png"},
        "qrcode": {"image/png": ".png"},
        "logo": ALLOWED_IMAGE_FORMATS,
    }

    # Security: Maximum file size limits (in bytes)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_BARCODE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_QRCODE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5 MB

    @staticmethod
    def safe_slug(value: str | None) -> str:
        """
        Create a safe slug for S3 keys.

        We don't rely on Django slugify here to keep shared layer independent.
        """
        if not value:
            return "unknown"
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = re.sub(r"-{2,}", "-", value).strip("-")
        return value or "unknown"

    @classmethod
    def build_named_filename(
        cls,
        prefix: str,
        name: str | None = None,
        entity_id: str | None = None,
        extra: str | None = None,
    ) -> str:
        """
        Build a readable-but-unique filename base (without extension).

        Example: product-rice-2kg-<uuid>-1234567890123
        """
        parts: list[str] = [prefix]
        if name:
            parts.append(cls.safe_slug(name))
        if entity_id:
            parts.append(str(entity_id))
        if extra:
            parts.append(str(extra))
        return "-".join([p for p in parts if p])

    def __init__(self) -> None:
        """Initialize S3 service."""
        self.aws_access_key_id = getattr(settings, "AWS_ACCESS_KEY_ID", None)
        self.aws_secret_access_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
        self.aws_region_name = getattr(settings, "AWS_REGION_NAME", None)
        self.aws_bucket_name = getattr(settings, "AWS_BUCKET_NAME", None)

        if not all(
            [
                self.aws_access_key_id,
                self.aws_secret_access_key,
                self.aws_region_name,
                self.aws_bucket_name,
            ]
        ):
            logger.warning("S3 credentials not fully configured. S3 uploads will fail.")

        self._s3_client = None

    @property
    def s3_client(self):
        """Get or create S3 client."""
        if self._s3_client is None:
            if not all([self.aws_access_key_id, self.aws_secret_access_key, self.aws_region_name]):
                raise BaseAPIException(
                    detail="AWS S3 credentials are not configured.",
                    code="S3_NOT_CONFIGURED",
                    status_code=500,
                )

            try:
                self._s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.aws_region_name,
                )
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
                raise BaseAPIException(
                    detail="Failed to initialize S3 client. Please check your AWS credentials.",
                    code="S3_INITIALIZATION_FAILED",
                    status_code=500,
                    details={"error": str(e)},
                ) from e
        return self._s3_client

    def _extract_key_from_s3_url(self, file_url: str) -> str | None:
        """
        Extract S3 object key from a stored URL.

        Supports:
        - https://bucket.s3.region.amazonaws.com/key
        - https://bucket.s3.amazonaws.com/key
        - https://s3.region.amazonaws.com/bucket/key
        """
        if not file_url:
            return None

        try:
            parsed = urlparse(file_url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lstrip("/")
            if self.aws_bucket_name and host.startswith(f"{self.aws_bucket_name}."):
                return path or None

            if self.aws_bucket_name and path.startswith(f"{self.aws_bucket_name}/"):
                return path[len(self.aws_bucket_name) + 1 :] or None

            if "amazonaws.com" not in file_url and "/" in file_url:
                return file_url.lstrip("/") or None

            return path or None
        except Exception:
            return None

    def generate_presigned_get_url(self, file_url: str, expires_in: int = 86400) -> str | None:
        """
        Generate a temporary pre-signed GET URL for a private S3 object.

        Returns None if the key cannot be extracted or if signing fails.
        """
        key = self._extract_key_from_s3_url(file_url)
        if not key:
            return None

        try:
            return self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.aws_bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception:
            return None

    def validate_file_format(self, file: BinaryIO, file_type: str = "image") -> str:
        """
        Validate the uploaded file format.

        Args:
            file: File object to validate
            file_type: Type of file (image, barcode, logo)

        Returns:
            File extension

        Raises:
            BaseAPIException: If the file format is not allowed
        """
        if not hasattr(file, "content_type"):
            raise BaseAPIException(
                detail="File must have content_type attribute.",
                code="INVALID_FILE",
                status_code=400,
            )

        allowed_formats = self.ALLOWED_FILE_TYPES.get(file_type, self.ALLOWED_IMAGE_FORMATS)

        if file.content_type not in allowed_formats:
            raise BaseAPIException(
                detail=f"Invalid file format: {file.content_type}. Allowed formats: {', '.join(allowed_formats.keys())}",
                code="INVALID_FILE_FORMAT",
                status_code=400,
                details={
                    "content_type": file.content_type,
                    "allowed_formats": list(allowed_formats.keys()),
                },
            )

        return allowed_formats[file.content_type]

    def upload_file(
        self,
        file: BinaryIO,
        folder: str,
        filename: str | None = None,
        file_type: str = "image",
    ) -> str:
        """
        Upload a file to S3.

        Args:
            file: File object to upload
            folder: S3 folder path (e.g., "products", "barcodes", "logos")
            filename: Optional base name for the file
            file_type: Type of file (image, barcode, logo)

        Returns:
            Public URL of the uploaded file

        Raises:
            BaseAPIException: If upload fails
        """
        if not file:
            raise BaseAPIException(
                detail="File is required.",
                code="FILE_REQUIRED",
                status_code=400,
            )

        try:
            max_size = {
                "image": self.MAX_IMAGE_SIZE,
                "barcode": self.MAX_BARCODE_SIZE,
                "qrcode": self.MAX_QRCODE_SIZE,
                "logo": self.MAX_LOGO_SIZE,
            }.get(file_type, self.MAX_FILE_SIZE)

            if hasattr(file, "size") and file.size > max_size:
                max_size_mb = max_size / (1024 * 1024)
                raise BaseAPIException(
                    detail=f"File size exceeds maximum allowed size of {max_size_mb:.1f}MB",
                    code="FILE_TOO_LARGE",
                    status_code=400,
                )
            # Validate file format
            file_extension = self.validate_file_format(file, file_type)

            # Generate filename
            if filename:
                file_name = f"{folder}/{filename}{file_extension}"
            else:
                file_name = f"{folder}/{uuid.uuid4()}{file_extension}"

            # Upload to S3
            self.s3_client.upload_fileobj(
                file,
                self.aws_bucket_name,
                file_name,
                ExtraArgs={"ContentType": file.content_type},
            )

            # Generate public URL
            file_url = (
                f"https://{self.aws_bucket_name}.s3."
                f"{self.aws_region_name}.amazonaws.com/{file_name}"
            )

            logger.info(f"File successfully uploaded to S3: {file_url}")
            return file_url

        except NoCredentialsError as e:
            logger.error("AWS credentials are missing.")
            raise BaseAPIException(
                detail="AWS S3 credentials are missing. Please configure AWS credentials.",
                code="S3_CREDENTIALS_MISSING",
                status_code=500,
                details={"error": str(e)},
            ) from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 upload failed: {error_code} - {error_message}")
            raise BaseAPIException(
                detail=f"S3 upload failed: {error_message}",
                code="S3_UPLOAD_FAILED",
                status_code=500,
                details={"error_code": error_code, "error": str(e)},
            ) from e
        except BaseAPIException:
            # Re-raise BaseAPIException as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {str(e)}", exc_info=True)
            raise BaseAPIException(
                detail="An unexpected error occurred during file upload. Please try again later.",
                code="S3_UPLOAD_ERROR",
                status_code=500,
                details={"error": str(e)},
            ) from e

    def upload_image(
        self,
        file: BinaryIO,
        folder: str = "products",
        filename: str | None = None,
    ) -> str:
        """
        Upload an image to S3.

        Args:
            file: Image file to upload
            folder: S3 folder path
            filename: Optional base name for the file

        Returns:
            Public URL of the uploaded image
        """
        return self.upload_file(file, folder=folder, filename=filename, file_type="image")

    def upload_barcode_image(
        self,
        barcode_image: BytesIO,
        barcode_value: str,
        filename: str | None = None,
    ) -> str:
        """
        Upload a barcode image to S3.

        Args:
            barcode_image: Barcode image as BytesIO
            barcode_value: Barcode value for filename

        Returns:
            Public URL of the uploaded barcode image
        """
        # Set content type for BytesIO
        barcode_image.content_type = "image/png"
        filename_base = filename or f"barcode-{barcode_value}"
        return self.upload_file(
            barcode_image,
            folder="barcodes",
            filename=filename_base,
            file_type="barcode",
        )

    def upload_qr_code_image(
        self,
        qr_image: BytesIO,
        filename: str,
    ) -> str:
        """
        Upload a QR code image to a dedicated S3 folder.
        """
        qr_image.content_type = "image/png"
        return self.upload_file(
            qr_image,
            folder="qrcodes",
            filename=filename,
            file_type="qrcode",
        )

    def upload_logo(
        self,
        file: BinaryIO,
        business_id: str,
        business_name: str | None = None,
    ) -> str:
        """
        Upload a business logo to S3.

        Args:
            file: Logo file to upload
            business_id: Business ID for filename

        Returns:
            Public URL of the uploaded logo
        """
        filename = self.build_named_filename(
            prefix="business-logo",
            name=business_name,
            entity_id=business_id,
        )
        return self.upload_file(
            file,
            folder="logos",
            filename=filename,
            file_type="logo",
        )

    def delete_file(self, file_url: str) -> None:
        """
        Delete a file from S3.

        Args:
            file_url: S3 URL of the file to delete

        Raises:
            BaseAPIException: If deletion fails
        """
        try:
            # Extract key from URL
            # URL format: https://bucket.s3.region.amazonaws.com/key
            if ".amazonaws.com/" in file_url:
                key = file_url.split(".amazonaws.com/")[1]
            else:
                raise BaseAPIException(
                    detail="Invalid S3 URL format.",
                    code="INVALID_S3_URL",
                    status_code=400,
                )

            self.s3_client.delete_object(Bucket=self.aws_bucket_name, Key=key)
            logger.info(f"File successfully deleted from S3: {file_url}")

        except BaseAPIException:
            # Re-raise BaseAPIException as-is
            raise
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 deletion failed: {error_code} - {error_message}")
            raise BaseAPIException(
                detail=f"S3 deletion failed: {error_message}",
                code="S3_DELETION_FAILED",
                status_code=500,
                details={"error_code": error_code, "error": str(e)},
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during S3 deletion: {str(e)}", exc_info=True)
            raise BaseAPIException(
                detail="An unexpected error occurred during file deletion. Please try again later.",
                code="S3_DELETION_ERROR",
                status_code=500,
                details={"error": str(e)},
            ) from e

    def delete_file_safe(self, file_url: str) -> bool:
        """
        Delete a file from S3 safely (returns boolean instead of raising exception).

        Args:
            file_url: S3 URL of the file to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            # Extract key from URL
            if ".amazonaws.com/" in file_url:
                key = file_url.split(".amazonaws.com/")[1]
            else:
                logger.warning(f"Invalid S3 URL format: {file_url}")
                return False

            self.s3_client.delete_object(Bucket=self.aws_bucket_name, Key=key)
            logger.info(f"File successfully deleted from S3: {file_url}")
            return True

        except Exception as e:
            logger.warning(f"Failed to delete file from S3: {file_url}, error: {str(e)}")
            return False
