"""The same object keys work with private MinIO and S3 buckets."""

import os
from functools import lru_cache
from io import BytesIO

from .settings import get_settings, required


class MinioStorage:
    def __init__(self, bucket: str):
        from minio import Minio

        self.bucket = bucket
        self.client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=required("MINIO_ACCESS_KEY"),
            secret_key=required("MINIO_SECRET_KEY"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )

    def ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload(self, key: str, data: bytes, content_type: str):
        self.client.put_object(
            self.bucket, key, BytesIO(data), len(data), content_type=content_type
        )

    def download(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def download_url(self, key: str) -> None:
        # The API serves local images because the browser cannot resolve 'minio'.
        return None


class S3Storage:
    def __init__(self, bucket: str):
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3")

    def ensure_bucket(self):
        # Terraform creates the AWS bucket.
        pass

    def upload(self, key: str, data: bytes, content_type: str):
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )

    def download(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def download_url(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=300
        )


@lru_cache
def get_storage():
    settings = get_settings()
    storage_class = S3Storage if settings.app_env == "aws" else MinioStorage
    return storage_class(settings.images_bucket)
