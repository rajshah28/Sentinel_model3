"""
Seeds cameras that have no demo footage attached (STATIC entries in
app.config.VENDOR_SOURCES) so the GIS view shows a realistic statewide
spread including at least one offline camera, not just the 3 that have
live demo footage wired through them.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import VENDOR_SOURCES
from app.db.database import SessionLocal
from app.db.models import Camera


def main():
    db = SessionLocal()
    try:
        for src in VENDOR_SOURCES:
            if src["kind"] != "STATIC":
                continue
            existing = db.query(Camera).filter(Camera.id == src["camera_id"]).first()
            if existing:
                continue
            db.add(Camera(
                id=src["camera_id"],
                department=src["department"],
                vendor="VendorD-Municipal-NVR",  # a 4th distinct vendor, status-only (no footage tonight)
                protocol="onvif_profile_s",
                location_name=src["location_name"],
                latitude=src["latitude"],
                longitude=src["longitude"],
                status=src["status"],
            ))
        db.commit()
        print("Static cameras seeded:", db.query(Camera).count(), "total cameras")
    finally:
        db.close()


if __name__ == "__main__":
    main()
