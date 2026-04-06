from abc import ABC, abstractmethod
from io import BytesIO
from typing import Optional


class IFileStorage(ABC):
    """Port for object storage operations (MinIO, S3, etc.)."""

    @abstractmethod
    def upload(
        self,
        bucket: str,
        key: str,
        data: BytesIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file and return the storage key."""
        ...

    @abstractmethod
    def get_presigned_url(
        self, bucket: str, key: str, expires_seconds: int = 3600
    ) -> str:
        """Generate a presigned download URL."""
        ...

    @abstractmethod
    def delete(self, bucket: str, key: str) -> None:
        """Delete an object."""
        ...
