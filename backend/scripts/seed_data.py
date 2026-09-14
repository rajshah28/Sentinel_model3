"""
Seeds the watchlist and two demo users (admin + department-user).

Crucially, the watchlist includes plate 'BGY888', which is the plate
verified (Phase 2 ANPR test) to be reliably read from the real Vendor B
demo footage (data/videos/vendorB_parking.mp4, plate reads as 'B GY 888'),
so the alert-match demo is real and reproducible, not staged.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.security import hash_password
from app.db.database import SessionLocal
from app.db.models import User, WatchlistRecord


def main():
    db = SessionLocal()
    try:
        if not db.query(WatchlistRecord).filter(WatchlistRecord.plate_text == "BGY888").first():
            db.add(WatchlistRecord(
                plate_text="BGY888",
                reason="Stolen Vehicle - FIR #GJ/DHD/2026/00417",
                vehicle_description="Grey BMW M3, sedan",
                added_by_department="Dahod City Police",
                priority="high",
            ))
        if not db.query(WatchlistRecord).filter(WatchlistRecord.plate_text == "GJ06XY1234").first():
            db.add(WatchlistRecord(
                plate_text="GJ06XY1234",
                reason="Wanted - Robbery Case #GJ/VLS/2026/00982",
                vehicle_description="White Maruti Swift, hatchback",
                added_by_department="Valsad Traffic Police",
                priority="high",
            ))
        if not db.query(WatchlistRecord).filter(WatchlistRecord.plate_text == "GJ10AB5566").first():
            db.add(WatchlistRecord(
                plate_text="GJ10AB5566",
                reason="Stolen Vehicle - FIR #GJ/JAM/2026/00201",
                vehicle_description="Black Honda City, sedan",
                added_by_department="Jamnagar City Police",
                priority="medium",
            ))

        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(
                username="admin",
                hashed_password=hash_password("Sentinel@2026"),
                role="admin",
                department="Home Department (State HQ)",
            ))
        if not db.query(User).filter(User.username == "dahod_operator").first():
            db.add(User(
                username="dahod_operator",
                hashed_password=hash_password("Dahod@2026"),
                role="department-user",
                department="Dahod City Police",
            ))

        db.commit()
        print("Seeded watchlist and users.")
        print("Watchlist entries:", db.query(WatchlistRecord).count())
        print("Users:", db.query(User).count())
    finally:
        db.close()


if __name__ == "__main__":
    main()
