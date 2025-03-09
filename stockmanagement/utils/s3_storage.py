from __future__ import annotations

import logging
import os
import uuid

import boto3
from botocore.exceptions import ClientError
from botocore.exceptions import NoCredentialsError
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


def upload_file_to_s3(file):
    """
    Upload an image to S3 after validating its format.

    :param file: File object to upload
    :return: Public URL of the uploaded image
    """
    if not file:
        return None

    # Vérifier le format de l'image
    file_extension = validate_image_format(file)

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
        logger.info(f"Image successfully uploaded to S3: {image_url}")
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
