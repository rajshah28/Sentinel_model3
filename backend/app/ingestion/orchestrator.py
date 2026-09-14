"""
Ingestion orchestrator: runs each vendor adapter's frame stream through
the ANPR pipeline and publishes DetectionEvents onto the bus. This is
the only module that talks to both adapters and the ANPR pipeline --
the correlation engine downstream only ever sees bus events.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from app.adapters.base import VendorAdapter
from app.anpr.pipeline import detect_and_read_plates
from app.bus.event_bus import Topics, bus
from app.db.database import SessionLocal
from app.db.models import Camera
from app.models.schema import DetectionEvent

logger = logging.getLogger("sentinel.ingestion")


def upsert_camera(adapter: VendorAdapter) -> None:
    info = adapter.get_camera_info()
    db = SessionLocal()
    try:
        existing = db.query(Camera).filter(Camera.id == info.camera_id).first()
        if existing:
            existing.status = info.status.value
        else:
            db.add(Camera(
                id=info.camera_id,
                department=info.department,
                vendor=info.vendor,
                protocol=info.protocol.value,
                location_name=info.location_name,
                latitude=info.latitude,
                longitude=info.longitude,
                status=info.status.value,
            ))
        db.commit()
    finally:
        db.close()


async def ingest_adapter(
    adapter: VendorAdapter,
    min_conf: float = 0.2,
    max_duration_sec: Optional[float] = None,
    max_frames: Optional[int] = None,
) -> int:
    """
    Run one adapter's frame stream through ANPR, publishing a
    DetectionEvent per plate read.

    For finite sources (vendors A/B/C, which read a fixed local file)
    this naturally runs to completion when the generator ends, exactly
    as before -- max_duration_sec/max_frames default to None and change
    nothing about that behavior.

    For a live/infinite source (vendor D, the government grid, which
    has no end-of-stream in the normal case per the integration spec)
    a caller that needs a bounded capture window -- e.g. the report
    generator -- passes max_duration_sec and/or max_frames, and this
    function stops iterating (closing the adapter's capture via its own
    generator cleanup) once either limit is hit, rather than running
    forever.
    """
    upsert_camera(adapter)
    info = adapter.get_camera_info()
    emitted = 0
    frame_count = 0
    start = time.monotonic()

    async for frame in adapter.frames():
        results = detect_and_read_plates(frame.frame_path, min_conf=min_conf)
        for r in results:
            event = DetectionEvent(
                event_id=str(uuid.uuid4()),
                camera_id=frame.camera_id,
                vendor=frame.vendor,
                department=info.department,
                timestamp=frame.timestamp,
                plate_text=r.plate_text,
                plate_confidence=r.plate_confidence,
                vehicle_bbox=r.vehicle_bbox,
                plate_bbox=r.plate_bbox,
                frame_path=frame.frame_path,
            )
            await bus.publish(Topics.DETECTIONS, event)
            emitted += 1
            logger.info("detection camera=%s plate=%s conf=%.2f",
                        event.camera_id, event.plate_text, event.plate_confidence)

        frame_count += 1
        if max_frames is not None and frame_count >= max_frames:
            logger.info("ingest_adapter: reached max_frames=%d, stopping capture for %s",
                        max_frames, adapter.get_camera_info().camera_id)
            break
        if max_duration_sec is not None and (time.monotonic() - start) >= max_duration_sec:
            logger.info("ingest_adapter: reached max_duration_sec=%.1f, stopping capture for %s",
                        max_duration_sec, adapter.get_camera_info().camera_id)
            break

    return emitted
