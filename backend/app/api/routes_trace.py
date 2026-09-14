"""
Vehicle trace API: given a plate number, return the full timestamped
route/movement history of that vehicle across every camera (any vendor,
any department) it was detected on. This reads straight from the
detections table, which the correlation engine populates from bus
events regardless of which adapter/vendor produced the original frame
-- that's what makes a single, vendor-agnostic trace query possible.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas_api import TraceSightingOut, VehicleTraceResponse, frame_url
from app.api.security import get_current_user
from app.db.database import get_db
from app.db.models import Camera, DetectionRecord, User, WatchlistRecord

router = APIRouter(prefix="/api/trace", tags=["trace"])


def _clean_plate(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isalnum())


@router.get("/{plate_text}", response_model=VehicleTraceResponse)
def trace_vehicle(plate_text: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    clean = _clean_plate(plate_text)

    detections = (
        db.query(DetectionRecord)
        .filter(DetectionRecord.plate_text == clean)
        .order_by(DetectionRecord.timestamp.asc())
        .all()
    )

    if not detections:
        raise HTTPException(status_code=404, detail=f"No sightings found for plate '{clean}'")

    if user.role != "admin" and user.department:
        detections = [d for d in detections if d.department == user.department]
        if not detections:
            raise HTTPException(status_code=404, detail="No sightings found for plate in your department's cameras")

    camera_cache: dict[str, Camera] = {}
    route: list[TraceSightingOut] = []
    cameras_seen: list[str] = []

    for d in detections:
        cam = camera_cache.get(d.camera_id)
        if cam is None:
            cam = db.query(Camera).filter(Camera.id == d.camera_id).first()
            camera_cache[d.camera_id] = cam
        if cam is None:
            continue

        route.append(TraceSightingOut(
            camera_id=d.camera_id,
            department=d.department,
            location_name=cam.location_name,
            latitude=cam.latitude,
            longitude=cam.longitude,
            timestamp=d.timestamp,
            confidence=d.plate_confidence,
            frame_path=d.frame_path,
            frame_url=frame_url(d.frame_path),
        ))
        if d.camera_id not in cameras_seen:
            cameras_seen.append(d.camera_id)

    watchlist_hit = db.query(WatchlistRecord).filter(WatchlistRecord.plate_text == clean, WatchlistRecord.active == True).first()  # noqa: E712
    watchlist_match = None
    if watchlist_hit:
        watchlist_match = {
            "reason": watchlist_hit.reason,
            "vehicle_description": watchlist_hit.vehicle_description,
            "priority": watchlist_hit.priority,
            "added_by_department": watchlist_hit.added_by_department,
        }

    return VehicleTraceResponse(
        plate_text=clean,
        total_sightings=len(route),
        cameras_seen=cameras_seen,
        watchlist_match=watchlist_match,
        route=route,
    )
