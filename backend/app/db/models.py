import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="department-user")  # or "admin"
    department = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True)  # camera_id
    department = Column(String, nullable=False)
    vendor = Column(String, nullable=False)
    protocol = Column(String, nullable=False)
    location_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="online")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class WatchlistRecord(Base):
    __tablename__ = "watchlist"

    id = Column(String, primary_key=True, default=_uuid)
    plate_text = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=False)  # e.g. "Stolen Vehicle", "Wanted - Robbery Case #..."
    vehicle_description = Column(String, nullable=True)
    added_by_department = Column(String, nullable=True)
    priority = Column(String, default="high")  # low/medium/high
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DetectionRecord(Base):
    __tablename__ = "detections"

    id = Column(String, primary_key=True, default=_uuid)
    camera_id = Column(String, ForeignKey("cameras.id"), nullable=False, index=True)
    department = Column(String, nullable=False)
    plate_text = Column(String, nullable=False, index=True)
    plate_confidence = Column(Float, nullable=False)
    detection_confidence = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    frame_path = Column(String, nullable=True)


class AlertRecord(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=_uuid)
    camera_id = Column(String, nullable=False, index=True)
    department = Column(String, nullable=False)
    plate_text = Column(String, nullable=False, index=True)
    watchlist_record_id = Column(String, ForeignKey("watchlist.id"), nullable=False)
    reason = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    frame_path = Column(String, nullable=True)
    acknowledged = Column(Boolean, default=False)
