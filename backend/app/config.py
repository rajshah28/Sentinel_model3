import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Loads backend/.env if present (operator-managed; never written to or
# read by application code beyond this point -- the values below are
# read from os.environ exactly as if the operator had exported them in
# their own shell). Does not override any variable already present in
# the real environment.
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Government sandbox grid (Vendor D). Unset by default -- must be provided
# explicitly (never hardcoded, never accepted from any source other than
# direct user instruction) before the live adapter will attempt a
# connection. See app/adapters/vendor_d_govt_grid.py.
#
# Credentials (email/password) are read from environment only, and are
# never logged, printed, or included in any URL that gets logged -- see
# vendor_d_govt_grid.py's _redact_url() helper. Set these in your own
# shell or a .env file that is never passed to Claude Code as a literal
# string; docker-compose.yml reads them the same way.
GOVT_GRID_HOST = os.environ.get("SENTINEL_GOVT_GRID_HOST", "")
GOVT_GRID_EMAIL = os.environ.get("SENTINEL_GOVT_GRID_EMAIL", "")
GOVT_GRID_PASSWORD = os.environ.get("SENTINEL_GOVT_GRID_PASSWORD", "")
GOVT_GRID_CATALOGUE_URL = os.environ.get("SENTINEL_GOVT_GRID_CATALOGUE_URL", "")
# Fallback camera-id range, used ONLY if the catalogue HTTP endpoint
# can't be fetched programmatically (e.g. it requires a browser/cookie
# login session rather than basic auth or an API token -- confirmed to
# be the case for this grid's cameras.json). The integration doc itself
# states camera ids are "cam01 ... cam30", so this is not an inferred
# or guessed value, but the documented range applied directly. Set to
# empty to disable and require a real catalogue fetch instead.
#
# SENTINEL_GOVT_GRID_FALLBACK_IDS_OVERRIDE, if set, is a comma-separated
# explicit id list that replaces the full cam01..cam30 range -- useful
# once a reachability probe (scripts/probe_govt_grid_cameras.py) has
# identified which subset actually responds, so a capture run doesn't
# burn its whole time budget on dead camera ids.
_fallback_override = os.environ.get("SENTINEL_GOVT_GRID_FALLBACK_IDS_OVERRIDE", "")
if _fallback_override:
    GOVT_GRID_FALLBACK_CAMERA_IDS = [c.strip() for c in _fallback_override.split(",") if c.strip()]
elif os.environ.get("SENTINEL_GOVT_GRID_USE_FALLBACK_IDS", ""):
    GOVT_GRID_FALLBACK_CAMERA_IDS = [f"cam{n:02d}" for n in range(1, 31)]
else:
    GOVT_GRID_FALLBACK_CAMERA_IDS = []
_default_data_dir = os.path.join(os.path.dirname(BASE_DIR), "data")
DATA_DIR = os.environ.get("SENTINEL_DATA_DIR", _default_data_dir)
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
FRAMES_DIR = os.path.join(DATA_DIR, "frames")

VENDOR_SOURCES = [
    {
        "kind": "A",
        "camera_id": "CAM-VLS-01",
        "department": "Valsad Traffic Police",
        "location_name": "NH48 Valsad Bypass",
        "latitude": 20.5992,
        "longitude": 72.9342,
        "video_file": "vendorA_highway.mp4",
        "sample_every_sec": 2.0,
    },
    {
        "kind": "B",
        "camera_id": "CAM-DHD-01",
        "department": "Dahod City Police",
        "location_name": "Dahod Bus Stand Parking",
        "latitude": 22.8333,
        "longitude": 74.2667,
        "video_file": "vendorB_parking.mp4",
        "sample_every_sec": 1.0,
    },
    {
        "kind": "C",
        "camera_id": "CAM-SOM-01",
        "department": "Somnath Traffic Police",
        "location_name": "Somnath Temple Road Junction",
        "latitude": 20.8880,
        "longitude": 70.4013,
        "video_file": "vendorC_closeup.mp4",
        "sample_every_sec": 1.0,
    },
    # Extra cameras (no footage attached) purely to make the GIS/status
    # view show a realistic statewide spread of online/offline cameras.
    {
        "kind": "STATIC",
        "camera_id": "CAM-JAM-01",
        "department": "Jamnagar City Police",
        "location_name": "Jamnagar Bedi Gate Circle",
        "latitude": 22.4707,
        "longitude": 70.0577,
        "status": "online",
    },
    {
        "kind": "STATIC",
        "camera_id": "CAM-DWK-01",
        "department": "Dwarka Traffic Police",
        "location_name": "Dwarka Temple Approach Road",
        "latitude": 22.2442,
        "longitude": 68.9685,
        "status": "offline",
    },
]
