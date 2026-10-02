from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .database import Base

VALID_IMAGE_STATUSES = ("pending", "processing", "completed", "failed")


class ImageRecord(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    camera_model = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    processed_at = Column(DateTime, nullable=True)
