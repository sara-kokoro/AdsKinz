"""Presigned uploads to Cloudflare R2 for campaign creative images.

The backend never handles image bytes: it hands the browser a short-lived
signed PUT URL, the browser uploads directly to R2, and only the resulting
public URL is stored on the campaign row (a plain string column — no binary
data ever touches Postgres).
"""

from __future__ import annotations

import uuid
from typing import Any

from app.config import settings
from app.core.errors import ConfigurationError, ValidationError

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _assert_configured() -> None:
    if not (settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY):
        raise ConfigurationError("Image uploads require R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY.")
    if not settings.R2_PUBLIC_BASE_URL:
        raise ConfigurationError("Image uploads require R2_PUBLIC_BASE_URL.")


def _r2_client() -> Any:
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def create_upload_url(*, content_type: str, advertiser_id: uuid.UUID) -> dict[str, str]:
    """Return a presigned PUT URL and the final public URL for one image.

    The object key is namespaced by advertiser and a random id so uploads
    can never collide or be overwritten by another advertiser.
    """
    _assert_configured()
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise ValidationError(
            f"Unsupported image type '{content_type}'. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}."
        )

    key = f"creatives/{advertiser_id}/{uuid.uuid4().hex}.{ext}"
    client = _r2_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.R2_UPLOAD_URL_EXPIRY_SECONDS,
    )
    public_url = f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
    return {"upload_url": upload_url, "public_url": public_url, "content_type": content_type}
