from __future__ import annotations

import structlog
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class S3Client:
    """Client for AWS S3 object storage operations.

    Supports both real AWS S3 and MinIO (local development) via endpoint_url.
    """

    def __init__(
        self,
        bucket_name: str,
        region: str,
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.region = region
        self.endpoint_url = endpoint_url
        self._session = get_session()
        self._client_kwargs: dict = {
            "region_name": region,
        }
        if endpoint_url:
            self._client_kwargs["endpoint_url"] = endpoint_url
        if aws_access_key_id and aws_secret_access_key:
            self._client_kwargs["aws_access_key_id"] = aws_access_key_id
            self._client_kwargs["aws_secret_access_key"] = aws_secret_access_key

    def _get_client(self):
        """Create an async S3 client context manager."""
        return self._session.create_client("s3", **self._client_kwargs)

    async def generate_presigned_upload_url(
        self, key: str, content_type: str, expires_in: int = 3600
    ) -> dict:
        """Generate a presigned URL for uploading a file to S3.

        Returns a dict with 'url' and 'fields' for multipart form upload.
        """
        async with self._get_client() as client:
            response = await client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, 5 * 1024 * 1024 * 1024],  # up to 5 GB
                ],
                ExpiresIn=expires_in,
            )
            logger.info("presigned_upload_url_generated", key=key)
            return response

    async def generate_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a file from S3."""
        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url

    async def upload_file(self, key: str, data: bytes, content_type: str) -> None:
        """Upload file data to S3 under the specified key."""
        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.info("file_uploaded", key=key, size=len(data))

    async def upload_fileobj(self, key: str, fileobj, content_type: str) -> None:
        """Upload a file-like object to S3 (for streaming large files)."""
        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=fileobj,
                ContentType=content_type,
            )
            logger.info("fileobj_uploaded", key=key)

    async def download_file(self, key: str) -> bytes:
        """Download a file from S3 and return its contents."""
        async with self._get_client() as client:
            try:
                response = await client.get_object(
                    Bucket=self.bucket_name, Key=key
                )
                data = await response["Body"].read()
                logger.info("file_downloaded", key=key, size=len(data))
                return data
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    raise FileNotFoundError(f"S3 object not found: {key}") from e
                raise

    async def delete_file(self, key: str) -> None:
        """Delete a file from S3 by key."""
        async with self._get_client() as client:
            await client.delete_object(
                Bucket=self.bucket_name, Key=key
            )
            logger.info("file_deleted", key=key)

    async def file_exists(self, key: str) -> bool:
        """Check whether a file exists in S3 at the specified key."""
        async with self._get_client() as client:
            try:
                await client.head_object(Bucket=self.bucket_name, Key=key)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    return False
                raise

    async def get_file_metadata(self, key: str) -> dict:
        """Get metadata for an S3 object (size, content type, last modified)."""
        async with self._get_client() as client:
            try:
                response = await client.head_object(
                    Bucket=self.bucket_name, Key=key
                )
                return {
                    "size": response["ContentLength"],
                    "content_type": response.get("ContentType", ""),
                    "last_modified": response["LastModified"],
                    "etag": response.get("ETag", ""),
                }
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    raise FileNotFoundError(f"S3 object not found: {key}") from e
                raise

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[dict]:
        """List objects under a prefix in S3."""
        async with self._get_client() as client:
            response = await client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            return [
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                }
                for obj in response.get("Contents", [])
            ]

    async def copy_object(self, source_key: str, dest_key: str) -> None:
        """Copy an object within the same bucket."""
        async with self._get_client() as client:
            await client.copy_object(
                Bucket=self.bucket_name,
                Key=dest_key,
                CopySource={"Bucket": self.bucket_name, "Key": source_key},
            )
            logger.info("file_copied", source=source_key, dest=dest_key)


def get_s3_client() -> S3Client:
    """Factory to create an S3Client from application settings."""
    settings = get_settings()
    return S3Client(
        bucket_name=settings.s3_bucket_name,
        region=settings.aws_region,
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
