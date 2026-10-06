"""AWS S3 client wrapping boto3 behind the client abstraction."""

from __future__ import annotations

import asyncio
import os
import urllib.parse
from typing import Any

from dotenv import load_dotenv

from app.clients.base import BaseS3Client
from app.config.settings import Settings
from app.exceptions.client_exceptions import S3Error


class S3Client(BaseS3Client):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3

            load_dotenv(override=False)
            # Prefer the dotenv/process environment, then fall back to Settings.
            access_key = os.getenv("AWS_ACCESS_KEY_ID") or self._settings.aws_access_key_id
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or self._settings.aws_secret_access_key
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or self._settings.aws_region
            kwargs: dict[str, Any] = {"region_name": region}
            if access_key:
                kwargs["aws_access_key_id"] = access_key
            if secret_key:
                kwargs["aws_secret_access_key"] = secret_key
            self._client = boto3.client("s3", **kwargs)
            return self._client
        except Exception as exc:  # pragma: no cover - environment dependent
            raise S3Error(details={"reason": str(exc)}) from exc

    def _bucket(self) -> str:
        bucket = self._settings.aws_s3_bucket
        if not bucket:
            raise S3Error(details={"reason": "aws_s3_bucket not configured"})
        return bucket

    async def upload(self, file: bytes, key: str, content_type: str) -> str:
        bucket = self._bucket()
        client = self._get_client()

        def _upload() -> None:
            client.put_object(Bucket=bucket, Key=key, Body=file, ContentType=content_type)

        try:
            await asyncio.to_thread(_upload)
        except S3Error:
            raise
        except Exception as exc:
            raise S3Error(details={"key": key, "reason": str(exc)[:500]}) from exc
        return self._object_url(bucket, key)

    async def download(self, key: str) -> bytes:
        client = self._get_client()

        async def _download() -> bytes:
            response = client.get_object(Bucket=self._bucket(), Key=key)
            return response["Body"].read()

        try:
            return await asyncio.to_thread(_download)
        except Exception as exc:
            raise S3Error(details={"key": key, "reason": str(exc)[:500]}) from exc

    @staticmethod
    def _object_url(bucket: str, key: str) -> str:
        encoded = urllib.parse.quote(key, safe="/")
        return f"https://{bucket}.s3.amazonaws.com/{encoded}"
