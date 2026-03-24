from __future__ import annotations

import logging
import uuid

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from decouple import config
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_image_format(file):
    """
    Validate the uploaded file format.

    :param file: File object to validate
    :raises ValidationError: If the file format is not allowed
    :return: The valid file extension
    """
    allowed_image_formats = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }

    file_type = file.content_type
    if file_type not in allowed_image_formats:
        raise ValidationError(
            {
                "error": f"Invalid file format: {file_type}."
                f" Allowed formats: {list(allowed_image_formats.keys())}"
            }
        )
    return allowed_image_formats[file_type]


def upload_file_to_s3(file, filename: str = None):
    """
    Upload an image to S3 after validating its format.

    :param file: File object to upload
    :param filename: Optional base name for the file, if not provided a UUID will be
    :return: Public URL of the uploaded image
    """
    if not file:
        return None

    file_extension = validate_image_format(file)
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
        region_name=config("AWS_REGION_NAME"),
    )

    try:
        file_name = f"Products/{filename or 'image'}-{uuid.uuid4()}{file_extension}"

        s3_client.upload_fileobj(
            file.file,
            config("AWS_BUCKET_NAME"),
            file_name,
            ExtraArgs={"ContentType": file.content_type},
        )
        image_url = (
            f"https://{config('AWS_BUCKET_NAME')}.s3."
            f"{config('AWS_REGION_NAME')}.amazonaws.com/{file_name}"
        )
        logger.info(f"Image successfully uploaded to S3: {image_url}")
        return image_url

    except NoCredentialsError:
        logger.error("AWS credentials are missing.")
        raise ValidationError({"error": "AWS credentials are missing."}) from None
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise ValidationError({"error": f"S3 upload failed: {e}"}) from e
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise ValidationError(f"Unexpected error occurred: {str(e)}") from e
