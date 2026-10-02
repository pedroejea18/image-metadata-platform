from typing import Literal

from pydantic import BaseModel


class ImageUploadResponse(BaseModel):
    id: int
    filename: str
    status: Literal["pending", "processing", "completed", "failed"]
    width: int | None = None
    height: int | None = None
    camera_model: str | None = None
