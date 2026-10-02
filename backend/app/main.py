"""One API for both deployments; infrastructure is selected with APP_ENV."""

import logging
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from mimetypes import guess_type
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from common.queue import get_queue
from common.storage import get_storage

from .database import Base, engine, get_db
from .models import ImageRecord, VALID_IMAGE_STATUSES
from .schemas import ImageUploadResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    get_storage().ensure_bucket()
    get_queue()
    yield


app = FastAPI(title="Image Metadata API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def find_image(image_id: int, db: Session) -> ImageRecord:
    image = db.get(ImageRecord, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


def image_response(image: ImageRecord) -> ImageUploadResponse:
    return ImageUploadResponse(
        id=image.id, filename=image.filename, status=image.status,
        width=image.width, height=image.height, camera_model=image.camera_model,
    )


def serve_image(image: ImageRecord, folder: str):
    key = f"{folder}/{image.filename}"
    storage = get_storage()
    try:
        url = storage.download_url(key)
        if url:
            return RedirectResponse(url=url, status_code=307)
        data = storage.download(key)
    except Exception as exc:
        logging.exception("Failed to retrieve image %s", key)
        raise HTTPException(status_code=502, detail="Could not retrieve the image") from exc
    content_type = guess_type(image.filename)[0] or "application/octet-stream"
    return Response(content=data, media_type=content_type)


@app.get("/")
def read_root():
    # This is the endpoint checked by the ALB.
    return {"status": "ok"}


@app.get("/api/images/{image_id}", response_model=ImageUploadResponse)
def get_image(image_id: int, db: Session = Depends(get_db)):
    return image_response(find_image(image_id, db))


@app.get("/api/images/{image_id}/file")
def get_image_file(image_id: int, db: Session = Depends(get_db)):
    return serve_image(find_image(image_id, db), "originals")


@app.get("/api/images/{image_id}/thumbnail")
def get_image_thumbnail(image_id: int, db: Session = Depends(get_db)):
    image = find_image(image_id, db)
    if image.status != "completed":
        raise HTTPException(status_code=409, detail="Thumbnail is not ready")
    return serve_image(image, "thumbnails")


@app.post("/api/images/upload", response_model=ImageUploadResponse)
def upload_image(
    file: UploadFile = File(...),
    status: str | None = None,
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="The file must be an image")
    if status is not None and status not in VALID_IMAGE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="status must be one of: pending, processing, completed, failed",
        )
    contents = file.file.read()
    try:
        with PILImage.open(BytesIO(contents)) as image:
            image.verify()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The file is not a valid image") from exc

    extension = Path(file.filename or "image").suffix.lower() or ".bin"
    filename = f"{uuid.uuid4().hex}{extension}"
    try:
        get_storage().upload(f"originals/{filename}", contents, file.content_type)
    except Exception as exc:
        logging.exception("Failed to upload original %s", filename)
        raise HTTPException(status_code=502, detail="Could not save the image") from exc

    record = ImageRecord(filename=filename, status="processing")
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except Exception as exc:
        db.rollback()
        logging.exception("Failed to create image record")
        raise HTTPException(status_code=500, detail="Could not save the image record") from exc

    try:
        get_queue().send(record.id, filename)
    except Exception as exc:
        record.status = "failed"
        db.commit()
        logging.exception("Failed to enqueue image %s", record.id)
        raise HTTPException(status_code=502, detail="Could not queue the processing job") from exc
    return image_response(record)
