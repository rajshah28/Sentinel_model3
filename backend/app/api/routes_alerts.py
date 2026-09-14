from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas_api import AlertOut, WatchlistOut, frame_url
from app.api.security import get_current_user, require_admin
from app.db.database import get_db
from app.db.models import AlertRecord, User, WatchlistRecord

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(AlertRecord).order_by(AlertRecord.timestamp.desc())
    if user.role != "admin" and user.department:
        query = query.filter(AlertRecord.department == user.department)
    records = query.limit(limit).all()
    out = []
    for a in records:
        item = AlertOut.model_validate(a)
        item.frame_url = frame_url(a.frame_path)
        out.append(item)
    return out


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/watchlist", response_model=list[WatchlistOut])
def list_watchlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(WatchlistRecord).filter(WatchlistRecord.active == True).all()  # noqa: E712


@router.post("/watchlist", response_model=WatchlistOut)
def add_watchlist_entry(
    entry: WatchlistOut,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    record = WatchlistRecord(
        plate_text=entry.plate_text.upper().replace(" ", ""),
        reason=entry.reason,
        vehicle_description=entry.vehicle_description,
        added_by_department=user.department,
        priority=entry.priority,
        active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
