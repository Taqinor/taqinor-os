import logging

import boto3
from django.conf import settings

logger = logging.getLogger(__name__)


def get_minio_client():
    return boto3.client(
        's3',
        endpoint_url=f'http://{settings.MINIO_ENDPOINT}',
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name='us-east-1',  # required by boto3, ignored by MinIO
    )


def ensure_uploads_bucket() -> None:
    """Create the uploads bucket if it does not exist yet (idempotent, best-effort).

    N108 — mirrors ``apps.ventes.quote_engine.builder._ensure_pdf_bucket``: the
    PDF path already self-heals a missing bucket (head_bucket → create_bucket on
    miss), but the ``erp-uploads`` bucket (``settings.MINIO_BUCKET_UPLOADS``) had
    no equivalent, so on a fresh MinIO every attachment / avatar / company
    logo-signature / field-photo / voice-memo upload crashed with HTTP 500
    (NoSuchBucket). Call this immediately before any upload that writes to the
    uploads bucket. Best-effort: never raises (a create failure is logged and the
    subsequent upload surfaces the real error)."""
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET_UPLOADS
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        except Exception as exc:
            logger.warning("Could not ensure MinIO bucket %s: %s", bucket, exc)
