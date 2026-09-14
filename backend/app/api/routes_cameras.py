from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas_api import CameraOut
from app.api.security import get_current_user
from app.db.database import get_db
from app.db.models import Camera, User

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Camera)
    if user.role != "admin" and user.department:
        query = query.filter(Camera.department == user.department)
    return query.all()
