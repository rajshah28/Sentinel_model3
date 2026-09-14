"""
Clears detections and alerts (but keeps cameras/watchlist/users) so the
demo ingestion run can be repeated cleanly from a fresh state.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import SessionLocal
from app.db.models import AlertRecord, DetectionRecord


def main():
    db = SessionLocal()
    try:
        n_alerts = db.query(AlertRecord).delete()
        n_detections = db.query(DetectionRecord).delete()
        db.commit()
        print(f"Cleared {n_detections} detections and {n_alerts} alerts. "
              f"Cameras, watchlist, and users are untouched.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
