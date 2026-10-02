"""A common job payload for Redis and SQS."""

import json
from functools import lru_cache

from .settings import get_settings, required


@lru_cache
def get_redis():
    from redis import Redis

    settings = get_settings()
    return Redis(
        host=settings.redis_host, port=settings.redis_port, decode_responses=True
    )


class RedisQueue:
    def send(self, image_id: int, filename: str):
        get_redis().rpush(
            get_settings().redis_queue,
            json.dumps({"image_id": image_id, "filename": filename}),
        )


class SQSQueue:
    def __init__(self):
        import boto3

        self.queue_url = required("SQS_QUEUE_URL")
        self.client = boto3.client("sqs")

    def send(self, image_id: int, filename: str):
        self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({"image_id": image_id, "filename": filename}),
        )


@lru_cache
def get_queue():
    return SQSQueue() if get_settings().app_env == "aws" else RedisQueue()
