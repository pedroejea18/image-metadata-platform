"""Image processing is identical in local Docker and AWS Lambda."""

from io import BytesIO

from PIL import Image

from common.storage import get_storage

from .database import complete_image, get_filename


def process_image(message: dict):
    image_id = int(message["image_id"])
    filename = message.get("filename")
    key = message.get("s3_key")
    if not key:
        # Older Redis jobs contain only the image ID.
        filename = filename or get_filename(image_id)
        key = f"originals/{filename}"
    filename = key.rsplit("/", 1)[-1]

    storage = get_storage()
    data = storage.download(key)
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
        image_format = image.format or "JPEG"
        camera_model = None
        thumbnail = image.copy()
        try:
            thumbnail.thumbnail((300, 300))
            buffer = BytesIO()
            thumbnail.save(buffer, format=image_format)
        finally:
            thumbnail.close()

    content_type = Image.MIME.get(image_format, "application/octet-stream")
    storage.upload(f"thumbnails/{filename}", buffer.getvalue(), content_type)
    complete_image(image_id, width, height, camera_model)
