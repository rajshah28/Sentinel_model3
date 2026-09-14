from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas_api import LoginRequest, TokenResponse
from app.api.security import create_access_token, get_current_user, verify_password
from app.db.database import get_db
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(
        access_token=token, role=user.role, department=user.department, username=user.username,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role, "department": user.department}
