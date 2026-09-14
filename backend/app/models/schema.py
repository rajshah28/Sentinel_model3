"""
Common normalized schema that every vendor adapter must produce.
This is the contract of the federation layer: adapters translate
vendor-specific formats into these shapes, and nothing downstream
(bus, correlation engine, API) ever sees a vendor-specific field.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class VendorProtocol(str, Enum):
    RTSP_STREAM = "rtsp_stream"       # Vendor A style: continuous stream reader
    FILE_BATCH = "file_batch"         # Vendor B style: local video file batch reader
    SNAPSHOT_POLL = "snapshot_poll"   # Vendor C style: image-sequence / snapshot API poller


class CameraStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class CameraInfo(BaseModel):
    """Normalized camera/feed descriptor, regardless of source vendor."""
    camera_id: str
    department: str
    vendor: str
    protocol: VendorProtocol
    location_name: str
    latitude: float
    longitude: float
    status: CameraStatus = CameraStatus.ONLINE


class NormalizedFrame(BaseModel):
    """One frame emitted by any adapter, in a common shape."""
    camera_id: str
    vendor: str
    frame_index: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    width: int
    height: int
    frame_path: str  # path to the extracted/saved frame image on disk


class DetectionEvent(BaseModel):
    """Emitted by the ANPR pipeline onto the bus after processing a frame."""
    event_id: str
    camera_id: str
    vendor: str
    department: str
    timestamp: datetime
    plate_text: str
    plate_confidence: float
    vehicle_bbox: Optional[list[float]] = None
    plate_bbox: Optional[list[float]] = None
    frame_path: str


class AlertEvent(BaseModel):
    """Emitted by the correlation engine when a detection matches the watchlist."""
    alert_id: str
    camera_id: str
    department: str
    timestamp: datetime
    plate_text: str
    watchlist_record_id: str
    reason: str
    confidence: float
    frame_path: str


class VehicleSighting(BaseModel):
    """A single confirmed sighting used to build cross-camera vehicle traces."""
    sighting_id: str
    plate_text: str
    camera_id: str
    department: str
    location_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    confidence: float
    frame_path: str
