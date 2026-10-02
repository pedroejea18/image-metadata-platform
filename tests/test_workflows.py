"""Regression tests for local/AWS routing, job compatibility and processing."""

import json
import os
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database import Base, get_db
from common.queue import get_queue, get_redis
from common.settings import get_postgres_password, get_settings
from common.storage import get_storage
from worker.app import lambda_handler, processing


def png_bytes():
    buffer = BytesIO()
    with Image.new("RGB", (600, 400), "blue") as image:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def clear_caches():
    for factory in (get_settings, get_postgres_password, get_storage, get_queue, get_redis):
        factory.cache_clear()


class APIWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        self.storage = Mock()
        self.storage.download_url.return_value = None
        self.storage.download.return_value = png_bytes()
        self.queue = Mock()

        def database():
            with Session(self.engine) as session:
                yield session

        main.app.dependency_overrides[get_db] = database
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.storage_patch = patch.object(main, "get_storage", return_value=self.storage)
        self.queue_patch = patch.object(main, "get_queue", return_value=self.queue)
        for patcher in (self.engine_patch, self.storage_patch, self.queue_patch):
            patcher.start()
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        main.app.dependency_overrides.clear()
        for patcher in (self.queue_patch, self.storage_patch, self.engine_patch):
            patcher.stop()
        self.engine.dispose()

    def upload(self):
        return self.client.post(
            "/api/images/upload", files={"file": ("example.png", png_bytes(), "image/png")}
        )

    def test_upload_queues_the_stored_filename_and_id(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        record = response.json()
        self.assertEqual(record["status"], "processing")
        self.queue.send.assert_called_once_with(record["id"], record["filename"])
        self.assertEqual(self.storage.upload.call_args.args[0], f"originals/{record['filename']}")
        self.assertEqual(self.client.get(f"/api/images/{record['id']}").status_code, 200)

    def test_local_download_and_thumbnail_readiness(self):
        record = self.upload().json()
        response = self.client.get(f"/api/images/{record['id']}/file")
        self.assertEqual(response.content, png_bytes())
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(self.client.get(f"/api/images/{record['id']}/thumbnail").status_code, 409)
        with Session(self.engine) as session:
            image = session.get(main.ImageRecord, record["id"])
            image.status = "completed"
            session.commit()
        self.assertEqual(self.client.get(f"/api/images/{record['id']}/thumbnail").status_code, 200)
        self.storage.download.assert_called_with(f"thumbnails/{record['filename']}")

    def test_aws_download_redirects_to_private_signed_url(self):
        record = self.upload().json()
        self.storage.download_url.return_value = "https://example.invalid/signed-object"
        response = self.client.get(f"/api/images/{record['id']}/file", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "https://example.invalid/signed-object")
        self.storage.download.assert_not_called()

    def test_invalid_image_is_not_uploaded_or_queued(self):
        response = self.client.post(
            "/api/images/upload", files={"file": ("invalid.png", b"not an image", "image/png")}
        )
        self.assertEqual(response.status_code, 400)
        self.storage.upload.assert_not_called()
        self.queue.send.assert_not_called()

    def test_queue_failure_marks_record_failed(self):
        self.queue.send.side_effect = RuntimeError("queue unavailable")
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.upload().status_code, 502)
        with Session(self.engine) as session:
            self.assertEqual(session.query(main.ImageRecord).one().status, "failed")


class WorkerTests(unittest.TestCase):
    def test_current_and_legacy_jobs_generate_the_same_thumbnail(self):
        for message in (
            {"image_id": 7, "filename": "example.png"},
            {"image_id": 7, "s3_key": "originals/example.png"},
            {"image_id": 7},
        ):
            with self.subTest(message=message):
                storage = Mock()
                storage.download.return_value = png_bytes()
                with patch.object(processing, "get_storage", return_value=storage), \
                     patch.object(processing, "get_filename", return_value="example.png"), \
                     patch.object(processing, "complete_image") as complete:
                    processing.process_image(message)
                storage.download.assert_called_once_with("originals/example.png")
                key, thumbnail, content_type = storage.upload.call_args.args
                self.assertEqual(key, "thumbnails/example.png")
                self.assertEqual(content_type, "image/png")
                with Image.open(BytesIO(thumbnail)) as image:
                    self.assertEqual(image.size, (300, 200))
                complete.assert_called_once_with(7, 600, 400, None)

    def test_failed_storage_does_not_mark_image_completed(self):
        storage = Mock()
        storage.download.return_value = png_bytes()
        storage.upload.side_effect = RuntimeError("storage unavailable")
        with patch.object(processing, "get_storage", return_value=storage), \
             patch.object(processing, "complete_image") as complete:
            with self.assertRaises(RuntimeError):
                processing.process_image({"image_id": 7, "filename": "example.png"})
        complete.assert_not_called()

    def test_lambda_decodes_sqs_messages_and_propagates_errors_for_retry(self):
        settings = Mock(app_env="aws")
        message = {"image_id": 7, "filename": "example.png"}
        event = {"Records": [{"body": json.dumps(message)}]}
        with patch.object(lambda_handler, "get_settings", return_value=settings), \
             patch.object(lambda_handler, "process_image") as process:
            lambda_handler.lambda_handler(event, None)
            process.assert_called_once_with(message)
            process.side_effect = RuntimeError("retry required")
            with self.assertRaises(RuntimeError):
                lambda_handler.lambda_handler(event, None)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        clear_caches()

    def tearDown(self):
        clear_caches()

    def test_local_initialization_never_contacts_aws(self):
        with patch.dict(os.environ, {
            "APP_ENV": "local", "MINIO_ACCESS_KEY": "testuser",
            "MINIO_SECRET_KEY": "testpassword", "POSTGRES_PASSWORD": "password",
        }, clear=True), patch("boto3.client") as aws_client:
            self.assertEqual(type(get_storage()).__name__, "MinioStorage")
            self.assertEqual(type(get_queue()).__name__, "RedisQueue")
            self.assertEqual(get_postgres_password(), "password")
            aws_client.assert_not_called()

    def test_aws_storage_queue_and_secret_use_the_configured_resources(self):
        storage = Mock()
        queue = Mock()
        secret = Mock()
        secret.get_secret_value.return_value = {"SecretString": "secret-password"}
        clients = {"s3": storage, "sqs": queue, "secretsmanager": secret}
        with patch.dict(os.environ, {
            "APP_ENV": "aws", "S3_BUCKET_IMAGES": "images-test",
            "SQS_QUEUE_URL": "https://sqs.example/test", "SECRET_ARN": "test-secret",
        }, clear=True), patch("boto3.client", side_effect=lambda name: clients[name]):
            get_storage().upload("originals/test.png", b"image", "image/png")
            get_queue().send(7, "test.png")
            self.assertEqual(get_postgres_password(), "secret-password")
        storage.put_object.assert_called_once_with(
            Bucket="images-test", Key="originals/test.png", Body=b"image", ContentType="image/png"
        )
        kwargs = queue.send_message.call_args.kwargs
        self.assertEqual(kwargs["QueueUrl"], "https://sqs.example/test")
        self.assertEqual(json.loads(kwargs["MessageBody"]), {"image_id": 7, "filename": "test.png"})
        secret.get_secret_value.assert_called_once_with(SecretId="test-secret")

    def test_redis_and_sqs_publish_the_same_message(self):
        from common.queue import RedisQueue, SQSQueue

        redis = Mock()
        sqs = Mock()
        with patch.dict(os.environ, {"APP_ENV": "local", "SQS_QUEUE_URL": "test-queue"}, clear=True), \
             patch("common.queue.get_redis", return_value=redis), \
             patch("boto3.client", return_value=sqs):
            RedisQueue().send(7, "test.png")
            SQSQueue().send(7, "test.png")
        self.assertEqual(
            json.loads(redis.rpush.call_args.args[1]),
            json.loads(sqs.send_message.call_args.kwargs["MessageBody"]),
        )


if __name__ == "__main__":
    unittest.main()
