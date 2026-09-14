"""
Cross-system event correlation engine.

This is the single place in the whole federation that decides "this is
a vehicle sighting" and "this is a watchlist match." It subscribes to
the bus (never called directly by adapters or the ANPR pipeline),
deduplicates repeated detections of the same plate on the same camera
within a short window, checks every detection against the watchlist,
and publishes VEHICLE_SIGHTINGS and ALERTS back onto the bus.

Because every department's adapter feeds detections through the same
bus topic in the same normalized schema, this engine correlates across
vendors/departments without knowing anything about their native formats.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.bus.event_bus import Topics, bus
from app.db.database import SessionLocal
from app.db.models import AlertRecord, Camera, DetectionRecord, WatchlistRecord
from app.models.schema import AlertEvent, DetectionEvent, VehicleSighting

logger = logging.getLogger("sentinel.correlation")

# Dedup window: same plate + same camera within this many seconds is
# treated as one continuous sighting, not N separate ones.
DEDUP_WINDOW_SECONDS = 10


class CorrelationEngine:
    def __init__(self):
        self._last_seen: dict[tuple[str, str], datetime] = {}

    def _is_duplicate(self, camera_id: str, plate_text: str, ts: datetime) -> bool:
        key = (camera_id, plate_text)
        last = self._last_seen.get(key)
        self._last_seen[key] = ts
        if last is None:
            return False
        return (ts - last) < timedelta(seconds=DEDUP_WINDOW_SECONDS)

    def _check_watchlist(self, db: Session, plate_text: str) -> WatchlistRecord | None:
        return (
            db.query(WatchlistRecord)
            .filter(WatchlistRecord.plate_text == plate_text, WatchlistRecord.active == True)  # noqa: E712
            .first()
        )

    def start(self) -> asyncio.Task:
        """
        Registers this engine's subscription synchronously (so no
        detection published after start() returns can be missed), then
        schedules the consume loop as a background task.
        """
        queue = bus.subscribe_now(Topics.DETECTIONS)
        return asyncio.create_task(self._consume(queue))

    async def _consume(self, queue: asyncio.Queue):
        logger.info("Correlation engine started, subscribed to %s", Topics.DETECTIONS)
        async for event in bus.drain(Topics.DETECTIONS, queue):
            await self._handle_detection(event)

    async def run(self):
        """Back-compat entrypoint: subscribes and consumes in one call."""
        async for event in bus.subscribe(Topics.DETECTIONS):
            await self._handle_detection(event)

    async def _handle_detection(self, event: DetectionEvent):
        db = SessionLocal()
        try:
            is_dup = self._is_duplicate(event.camera_id, event.plate_text, event.timestamp)

            db.add(DetectionRecord(
                id=event.event_id,
                camera_id=event.camera_id,
                department=event.department,
                plate_text=event.plate_text,
                plate_confidence=event.plate_confidence,
                detection_confidence=None,
                timestamp=event.timestamp,
                frame_path=event.frame_path,
            ))
            db.commit()

            camera = db.query(Camera).filter(Camera.id == event.camera_id).first()
            location_name = camera.location_name if camera else event.camera_id
            lat = camera.latitude if camera else 0.0
            lon = camera.longitude if camera else 0.0

            sighting = VehicleSighting(
                sighting_id=str(uuid.uuid4()),
                plate_text=event.plate_text,
                camera_id=event.camera_id,
                department=event.department,
                location_name=location_name,
                latitude=lat,
                longitude=lon,
                timestamp=event.timestamp,
                confidence=event.plate_confidence,
                frame_path=event.frame_path,
            )
            await bus.publish(Topics.VEHICLE_SIGHTINGS, sighting)

            if is_dup:
                return  # don't re-alert on the same continuous sighting

            watchlist_hit = self._check_watchlist(db, event.plate_text)
            if watchlist_hit:
                alert = AlertEvent(
                    alert_id=str(uuid.uuid4()),
                    camera_id=event.camera_id,
                    department=event.department,
                    timestamp=event.timestamp,
                    plate_text=event.plate_text,
                    watchlist_record_id=watchlist_hit.id,
                    reason=watchlist_hit.reason,
                    confidence=event.plate_confidence,
                    frame_path=event.frame_path,
                )
                db.add(AlertRecord(
                    id=alert.alert_id,
                    camera_id=alert.camera_id,
                    department=alert.department,
                    plate_text=alert.plate_text,
                    watchlist_record_id=alert.watchlist_record_id,
                    reason=alert.reason,
                    confidence=alert.confidence,
                    timestamp=alert.timestamp,
                    frame_path=alert.frame_path,
                ))
                db.commit()
                logger.warning("ALERT: plate=%s camera=%s reason=%s",
                                alert.plate_text, alert.camera_id, alert.reason)
                await bus.publish(Topics.ALERTS, alert)
        finally:
            db.close()


engine = CorrelationEngine()
