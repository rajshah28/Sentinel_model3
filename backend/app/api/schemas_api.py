import os
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.config import FRAMES_DIR


def frame_url(frame_path: Optional[str]) -> Optional[str]:
    """Converts a stored (possibly relative) frame_path into a /frames/... URL."""
    if not frame_path:
        return None
    real = os.path.realpath(frame_path)
    real_frames = os.path.realpath(FRAMES_DIR)
    if real.startswith(real_frames):
        return "/frames/" + os.path.relpath(real, real_frames).replace(os.sep, "/")
    return None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    department: Optional[str] = None
    username: str


class CameraOut(BaseModel):
    id: str
    department: str
    vendor: str
    protocol: str
    location_name: str
    latitude: float
    longitude: float
    status: str

    class Config:
        from_attributes = True


class AlertOut(BaseModel):
    id: str
    camera_id: str
    department: str
    plate_text: str
    reason: str
    confidence: float
    timestamp: datetime
    frame_path: Optional[str] = None
    frame_url: Optional[str] = None
    acknowledged: bool

    class Config:
        from_attributes = True


class TraceSightingOut(BaseModel):
    camera_id: str
    department: str
    location_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    confidence: float
    frame_path: Optional[str] = None
    frame_url: Optional[str] = None


class VehicleTraceResponse(BaseModel):
    plate_text: str
    total_sightings: int
    cameras_seen: list[str]
    watchlist_match: Optional[dict] = None
    route: list[TraceSightingOut]


class WatchlistOut(BaseModel):
    id: str
    plate_text: str
    reason: str
    vehicle_description: Optional[str] = None
    added_by_department: Optional[str] = None
    priority: str
    active: bool

    class Config:
        from_attributes = True


class IngestionStatus(BaseModel):
    running: bool
    cameras_ingested: list[str]
    total_detections_emitted: int
    last_run_finished: Optional[datetime] = None
