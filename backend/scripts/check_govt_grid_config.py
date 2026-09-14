"""
Confirms the government-grid config loaded from backend/.env without
ever printing the actual secret value -- only whether it's set, and a
masked preview (first char + length) so a typo can be spotted without
exposing the real password.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import (
    GOVT_GRID_CATALOGUE_URL,
    GOVT_GRID_EMAIL,
    GOVT_GRID_FALLBACK_CAMERA_IDS,
    GOVT_GRID_HOST,
    GOVT_GRID_PASSWORD,
)


def mask(value: str) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1] + f"  [len={len(value)}]"


def main():
    print("=== Government Grid Config (from backend/.env or environment) ===")
    print(f"HOST:            {GOVT_GRID_HOST or '(not set)'}")
    print(f"EMAIL:           {mask(GOVT_GRID_EMAIL)}")
    print(f"PASSWORD:        {mask(GOVT_GRID_PASSWORD)}")
    print(f"CATALOGUE_URL:   {GOVT_GRID_CATALOGUE_URL or '(not set, will default to /api/ingest)'}")
    print(f"FALLBACK_IDS:    {len(GOVT_GRID_FALLBACK_CAMERA_IDS)} ids configured" if GOVT_GRID_FALLBACK_CAMERA_IDS else "FALLBACK_IDS:    (disabled)")

    ready = bool(GOVT_GRID_HOST and GOVT_GRID_EMAIL and GOVT_GRID_PASSWORD)
    print(f"\nReady for a real connection attempt: {ready}")
    if not ready:
        missing = []
        if not GOVT_GRID_HOST:
            missing.append("SENTINEL_GOVT_GRID_HOST")
        if not GOVT_GRID_EMAIL:
            missing.append("SENTINEL_GOVT_GRID_EMAIL")
        if not GOVT_GRID_PASSWORD:
            missing.append("SENTINEL_GOVT_GRID_PASSWORD")
        print(f"Missing: {', '.join(missing)}")
        print("Create backend/.env with these set (see docs/05-cybersecurity-architecture.md).")


if __name__ == "__main__":
    main()
