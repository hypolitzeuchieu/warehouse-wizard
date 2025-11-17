"""S3 service for file uploads (images, barcodes, logos)."""

from __future__ import annotations

import logging
import uuid
from io import BytesIO
from typing import BinaryIO

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
        "logo": ALLOWED_IMAGE_FORMATS,
    }

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
                    detail="AWS S3 credentials are not configured. Please configure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION_NAME.",
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
        return self.upload_file(
            barcode_image,
            folder="barcodes",
            filename=f"barcode_{barcode_value}",
            file_type="barcode",
        )

    def upload_logo(
        self,
        file: BinaryIO,
        business_id: str,
    ) -> str:
        """
        Upload a business logo to S3.

        Args:
            file: Logo file to upload
            business_id: Business ID for filename

        Returns:
            Public URL of the uploaded logo
        """
        return self.upload_file(
            file,
            folder="logos",
            filename=f"business_{business_id}",
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
