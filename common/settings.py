"""Environment configuration. Local mode never needs AWS credentials."""

import os
from dataclasses import dataclass
from functools import lru_cache


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is not configured")
    return value


@dataclass(frozen=True)
class Settings:
    app_env: str
    images_bucket: str
    redis_host: str
    redis_port: int
    redis_queue: str


@lru_cache
def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "local").lower()
    if app_env not in {"local", "aws"}:
        raise RuntimeError("APP_ENV must be 'local' or 'aws'")
    return Settings(
        app_env=app_env,
        images_bucket=(required("S3_BUCKET_IMAGES") if app_env == "aws"
                       else os.getenv("MINIO_BUCKET_IMAGES", "images")),
        redis_host=os.getenv("REDIS_HOST", "redis"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_queue=os.getenv("REDIS_QUEUE_NAME", "image_jobs"),
    )


@lru_cache
def get_postgres_password() -> str:
    # Compose and ECS provide the password directly.
    password = os.getenv("POSTGRES_PASSWORD")
    if password:
        return password
    if get_settings().app_env == "aws":
        # Lambda reads the password from Secrets Manager.
        import boto3

        response = boto3.client("secretsmanager").get_secret_value(
            SecretId=required("SECRET_ARN")
        )
        return response["SecretString"]
    return required("POSTGRES_PASSWORD")


def postgres_options() -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST", "postgres"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": get_postgres_password(),
        "dbname": os.getenv("POSTGRES_DB", "image_metadata"),
    }
