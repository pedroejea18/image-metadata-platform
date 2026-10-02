"""Long-running Redis consumer for Docker Compose."""

import json
import logging
import time

from redis.exceptions import RedisError

from common.queue import get_redis
from common.settings import get_settings

from .database import fail_image
from .processing import process_image


def main():
    if get_settings().app_env != "local":
        raise RuntimeError("The Redis worker requires APP_ENV=local")
    client = get_redis()
    while True:
        try:
            item = client.blpop(get_settings().redis_queue, timeout=5)
        except RedisError:
            logging.exception("Redis connection failed")
            time.sleep(1)
            continue
        if item is None:
            continue
        image_id = None
        try:
            message = json.loads(item[1])
            if not isinstance(message, dict):
                message = {"image_id": int(message)}
            image_id = int(message["image_id"])
            process_image(message)
        except Exception:
            logging.exception("Failed to process image %s", image_id)
            if image_id is not None:
                try:
                    fail_image(image_id)
                except Exception:
                    logging.exception("Failed to update image status")


if __name__ == "__main__":
    main()
