"""MinIO model store — uploads and downloads versioned joblib artifacts."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import boto3
from ap_logging import get_logger
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

log = get_logger(__name__)


class ModelStore:
    """Thin wrapper around boto3 S3 client pointed at a MinIO instance."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self._bucket = bucket
        parsed = urlparse(endpoint)
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",  # MinIO ignores region but boto3 requires one
            use_ssl=parsed.scheme == "https",
        )

    # ------------------------------------------------------------------
    # Bucket lifecycle
    # ------------------------------------------------------------------

    def ensure_bucket(self) -> None:
        """Create the models bucket if it does not already exist."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket)
                log.info("bucket_created", bucket=self._bucket)
            else:
                raise

    # ------------------------------------------------------------------
    # Artifact storage
    # ------------------------------------------------------------------

    def upload(self, key: str, data: bytes) -> str:
        """Upload *data* to *key* inside the bucket. Returns the key."""
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=io.BytesIO(data),
            ContentType="application/octet-stream",
        )
        log.info("model_uploaded", bucket=self._bucket, key=key, size_bytes=len(data))
        return key

    def download(self, key: str) -> bytes:
        """Download artifact at *key* and return raw bytes."""
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        data: bytes = response["Body"].read()
        log.info("model_downloaded", bucket=self._bucket, key=key, size_bytes=len(data))
        return data

    def list_keys(self, prefix: str = "") -> list[str]:
        """Return all object keys under *prefix* (for inspection / DoD checks)."""
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    # ------------------------------------------------------------------
    # Key helper
    # ------------------------------------------------------------------

    @staticmethod
    def artifact_key(service: str, metric: str, model_id: str) -> str:
        """Canonical MinIO key for a model artifact."""
        return f"models/{service}/{metric}/{model_id}.joblib"
