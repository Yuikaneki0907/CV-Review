from datetime import timedelta
from io import BytesIO

from minio import Minio

from app.application.interfaces.file_storage import IFileStorage
from app.config import get_settings
from app.logger import get_logger

logger = get_logger("app.infrastructure.storage.minio")


class MinioFileStorage(IFileStorage):
    """MinIO implementation of IFileStorage."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
        self._ensure_bucket(settings.MINIO_BUCKET_NAME)

    def _ensure_bucket(self, bucket: str) -> None:
        """Create bucket if it does not exist."""
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)

    def upload(
        self,
        bucket: str,
        key: str,
        data: BytesIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        self._client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=data,
            length=length,
            content_type=content_type,
        )
        logger.info("Uploaded object: bucket=%s, key=%s, size=%d", bucket, key, length)
        return key

    def get_presigned_url(
        self, bucket: str, key: str, expires_seconds: int = 3600
    ) -> str:
        url = self._client.presigned_get_object(
            bucket_name=bucket,
            object_name=key,
            expires=timedelta(seconds=expires_seconds),
        )
        logger.debug("Generated presigned URL: bucket=%s, key=%s", bucket, key)
        return url

    def delete(self, bucket: str, key: str) -> None:
        self._client.remove_object(bucket_name=bucket, object_name=key)
        logger.info("Deleted object: bucket=%s, key=%s", bucket, key)
