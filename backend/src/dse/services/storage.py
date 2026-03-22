from __future__ import annotations

import json
from typing import Any

import structlog

from dse.config import settings
from dse.core.exceptions import StorageError

logger = structlog.get_logger(__name__)


class StorageService:
    """Object storage client for memory content persistence.

    Uses boto3 (S3 API) when STORAGE_ENDPOINT_URL is set (MinIO/S3),
    and google-cloud-storage when it's not (real GCS).
    """

    def __init__(self) -> None:
        self._bucket_name = settings.gcs_bucket_name
        self._s3_client: Any = None
        self._gcs_client: Any = None
        self._use_s3 = bool(settings.storage_endpoint_url)

    def _get_s3(self) -> Any:
        if self._s3_client is None:
            import boto3

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=settings.storage_endpoint_url,
                aws_access_key_id=settings.storage_access_key,
                aws_secret_access_key=settings.storage_secret_key,
                region_name="us-east-1",
            )
            # Ensure bucket exists
            try:
                self._s3_client.head_bucket(Bucket=self._bucket_name)
            except Exception:
                try:
                    self._s3_client.create_bucket(Bucket=self._bucket_name)
                    logger.info("storage.bucket_created", bucket=self._bucket_name)
                except Exception:
                    pass  # Bucket may already exist in a race
        return self._s3_client

    def _get_gcs(self) -> Any:
        if self._gcs_client is None:
            from google.cloud import storage

            self._gcs_client = storage.Client(project=settings.google_cloud_project)
        return self._gcs_client

    def _content_path(self, namespace: str, memory_id: str, ext: str = "txt") -> str:
        return f"memories/{namespace}/{memory_id}.{ext}"

    async def store_content(
        self,
        namespace: str,
        memory_id: str,
        content: str,
        *,
        content_type: str = "text/plain",
        ext: str = "txt",
    ) -> str:
        """Store memory content and return the storage path."""
        path = self._content_path(namespace, memory_id, ext)
        try:
            if self._use_s3:
                self._get_s3().put_object(
                    Bucket=self._bucket_name,
                    Key=path,
                    Body=content.encode("utf-8"),
                    ContentType=content_type,
                )
            else:
                client = self._get_gcs()
                bucket = client.bucket(self._bucket_name)
                blob = bucket.blob(path)
                blob.upload_from_string(content, content_type=content_type)

            logger.info("storage.stored", path=path, size=len(content))
            return f"gs://{self._bucket_name}/{path}"
        except Exception as e:
            logger.error("storage.store_failed", error=str(e), memory_id=memory_id)
            raise StorageError(f"Failed to store content: {e}") from e

    async def store_metadata(
        self,
        namespace: str,
        memory_id: str,
        metadata: dict[str, Any],
    ) -> str:
        """Store memory metadata as JSON."""
        path = f"memories/{namespace}/{memory_id}/metadata.json"
        body = json.dumps(metadata, ensure_ascii=False, indent=2)
        try:
            if self._use_s3:
                self._get_s3().put_object(
                    Bucket=self._bucket_name,
                    Key=path,
                    Body=body.encode("utf-8"),
                    ContentType="application/json",
                )
            else:
                client = self._get_gcs()
                bucket = client.bucket(self._bucket_name)
                blob = bucket.blob(path)
                blob.upload_from_string(body, content_type="application/json")

            return f"gs://{self._bucket_name}/{path}"
        except Exception as e:
            logger.error("storage.metadata_failed", error=str(e), memory_id=memory_id)
            raise StorageError(f"Failed to store metadata: {e}") from e

    async def fetch_content(self, content_path: str) -> str:
        """Fetch content from a gs:// path."""
        path = content_path.removeprefix(f"gs://{self._bucket_name}/")
        try:
            if self._use_s3:
                resp = self._get_s3().get_object(Bucket=self._bucket_name, Key=path)
                return resp["Body"].read().decode("utf-8")
            else:
                client = self._get_gcs()
                bucket = client.bucket(self._bucket_name)
                blob = bucket.blob(path)
                return blob.download_as_text()
        except Exception as e:
            logger.error("storage.fetch_failed", error=str(e), path=content_path)
            raise StorageError(f"Failed to fetch content: {e}") from e

    async def delete_content(self, namespace: str, memory_id: str) -> None:
        """Delete all content for a memory record."""
        prefix = f"memories/{namespace}/{memory_id}"
        try:
            if self._use_s3:
                s3 = self._get_s3()
                resp = s3.list_objects_v2(Bucket=self._bucket_name, Prefix=prefix)
                for obj in resp.get("Contents", []):
                    s3.delete_object(Bucket=self._bucket_name, Key=obj["Key"])
            else:
                client = self._get_gcs()
                bucket = client.bucket(self._bucket_name)
                blobs = list(bucket.list_blobs(prefix=prefix))
                for blob in blobs:
                    blob.delete()

            logger.info("storage.deleted", namespace=namespace, memory_id=memory_id)
        except Exception as e:
            logger.error("storage.delete_failed", error=str(e), memory_id=memory_id)
            raise StorageError(f"Failed to delete content: {e}") from e

    async def delete_namespace(self, namespace: str) -> None:
        """Delete ALL objects for a namespace (memories + provenance)."""
        prefix = f"memories/{namespace}/"
        try:
            if self._use_s3:
                s3 = self._get_s3()
                paginator = s3.get_paginator("list_objects_v2")
                deleted = 0
                for page in paginator.paginate(Bucket=self._bucket_name, Prefix=prefix):
                    objects = page.get("Contents", [])
                    if objects:
                        s3.delete_objects(
                            Bucket=self._bucket_name,
                            Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                        )
                        deleted += len(objects)
                # Also delete provenance files
                prov_prefix = f"provenance/{namespace}/"
                for page in paginator.paginate(Bucket=self._bucket_name, Prefix=prov_prefix):
                    objects = page.get("Contents", [])
                    if objects:
                        s3.delete_objects(
                            Bucket=self._bucket_name,
                            Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                        )
                        deleted += len(objects)
                logger.info("storage.namespace_deleted", namespace=namespace, objects=deleted)
            else:
                client = self._get_gcs()
                bucket = client.bucket(self._bucket_name)
                blobs = list(bucket.list_blobs(prefix=prefix))
                blobs += list(bucket.list_blobs(prefix=f"provenance/{namespace}/"))
                for blob in blobs:
                    blob.delete()
                logger.info("storage.namespace_deleted", namespace=namespace, objects=len(blobs))
        except Exception as e:
            logger.error("storage.namespace_delete_failed", error=str(e), namespace=namespace)
            raise StorageError(f"Failed to delete namespace content: {e}") from e


class MockStorageService(StorageService):
    """In-memory mock for testing."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._bucket_name = "mock-bucket"

    async def store_content(
        self,
        namespace: str,
        memory_id: str,
        content: str,
        *,
        content_type: str = "text/plain",
        ext: str = "txt",
    ) -> str:
        path = f"gs://mock-bucket/memories/{namespace}/{memory_id}.{ext}"
        self._store[path] = content
        return path

    async def store_metadata(
        self,
        namespace: str,
        memory_id: str,
        metadata: dict[str, Any],
    ) -> str:
        path = f"gs://mock-bucket/memories/{namespace}/{memory_id}/metadata.json"
        self._store[path] = json.dumps(metadata)
        return path

    async def fetch_content(self, content_path: str) -> str:
        content = self._store.get(content_path)
        if content is None:
            raise StorageError(f"Not found: {content_path}")
        return content

    async def delete_content(self, namespace: str, memory_id: str) -> None:
        prefix = f"gs://mock-bucket/memories/{namespace}/{memory_id}"
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._store[key]

    async def delete_namespace(self, namespace: str) -> None:
        keys_to_delete = [
            k
            for k in self._store
            if f"/memories/{namespace}/" in k or f"/provenance/{namespace}/" in k
        ]
        for key in keys_to_delete:
            del self._store[key]
