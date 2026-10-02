"""SQS-triggered Lambda entry point; failed batches retain AWS retry behavior."""

import json

from common.settings import get_settings

from .processing import process_image


def lambda_handler(event, context):
    if get_settings().app_env != "aws":
        raise RuntimeError("The Lambda worker requires APP_ENV=aws")
    for record in event["Records"]:
        process_image(json.loads(record["body"]))
