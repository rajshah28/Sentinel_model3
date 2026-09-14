"""
Ingestion control endpoint: lets the dashboard (or the demo script)
kick off a run of all demo vendor adapters through the real ANPR ->
bus -> correlation pipeline, and reports simple run status. This is
what the "how to reproduce the demo" README step calls.
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.govt_grid_catalogue import CatalogueError, fetch_catalogue, redact_url
from app.api.schemas_api import IngestionStatus
from app.api.security import require_admin
from app.config import GOVT_GRID_HOST
from app.db.models import User
from app.ingestion.adapter_factory import build_demo_adapters, build_govt_grid_adapters
from app.ingestion.orchestrator import ingest_adapter

logger = logging.getLogger("sentinel.ingestion.api")
router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

_state = {
    "running": False,
    "cameras_ingested": [],
    "total_detections_emitted": 0,
    "last_run_finished": None,
}


async def _run_all():
    _state["running"] = True
    _state["cameras_ingested"] = []
    _state["total_detections_emitted"] = 0
    try:
        for adapter in build_demo_adapters():
            n = await ingest_adapter(adapter, min_conf=0.2)
            _state["cameras_ingested"].append(adapter.get_camera_info().camera_id)
            _state["total_detections_emitted"] += n
    finally:
        _state["running"] = False
        _state["last_run_finished"] = datetime.now(timezone.utc)


@router.post("/run-demo", response_model=IngestionStatus)
async def run_demo(user: User = Depends(require_admin)):
    if not _state["running"]:
        asyncio.create_task(_run_all())
    return IngestionStatus(**_state)


@router.get("/status", response_model=IngestionStatus)
def status():
    return IngestionStatus(**_state)


# --- Government sandbox grid (Vendor D) -----------------------------------
#
# Kept deliberately separate from the run-demo/status endpoints above:
# this hits a real network host, can fail for real (unreachable host,
# no cameras live), and runs for a bounded capture window rather than
# "until the file ends" like vendors A/B/C.

_govt_state = {
    "running": False,
    "cameras_ingested": [],
    "total_detections_emitted": 0,
    "last_run_finished": None,
}


@router.get("/govt-grid/catalogue")
def govt_grid_catalogue(user: User = Depends(require_admin)):
    """Fetches and returns the live camera catalogue -- proves connectivity
    before attempting any RTSP connection."""
    if not GOVT_GRID_HOST:
        raise HTTPException(
            status_code=400,
            detail="SENTINEL_GOVT_GRID_HOST is not configured on this server.",
        )
    try:
        cameras = fetch_catalogue(GOVT_GRID_HOST)
    except CatalogueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "host": GOVT_GRID_HOST,
        "camera_count": len(cameras),
        "cameras": [
            # rtsp_url is redacted before it ever leaves the server: it
            # embeds live credentials (rtsp://email:password@host/...)
            # and must never reach a browser, log, or database row.
            {"id": c.camera_id, "location": c.location, "codec": c.codec,
             "live": c.live, "rtsp_url": redact_url(c.rtsp_url)}
            for c in cameras
        ],
    }


async def _run_govt_grid(duration_sec: float):
    _govt_state["running"] = True
    _govt_state["cameras_ingested"] = []
    _govt_state["total_detections_emitted"] = 0
    try:
        adapters = build_govt_grid_adapters()
        for adapter in adapters:
            n = await ingest_adapter(adapter, min_conf=0.2, max_duration_sec=duration_sec)
            _govt_state["cameras_ingested"].append(adapter.get_camera_info().camera_id)
            _govt_state["total_detections_emitted"] += n
    except CatalogueError as e:
        logger.error("govt grid ingestion failed: %s", e)
    finally:
        _govt_state["running"] = False
        _govt_state["last_run_finished"] = datetime.now(timezone.utc)


@router.post("/govt-grid/run", response_model=IngestionStatus)
async def run_govt_grid(duration_sec: float = 60.0, user: User = Depends(require_admin)):
    """
    Runs a bounded capture window (default 60s) against every camera in
    the live government sandbox catalogue, through the same ANPR -> bus
    -> correlation -> watchlist pipeline as the simulated vendors.
    """
    if not _govt_state["running"]:
        asyncio.create_task(_run_govt_grid(duration_sec))
    return IngestionStatus(**_govt_state)


@router.get("/govt-grid/status", response_model=IngestionStatus)
def govt_grid_status():
    return IngestionStatus(**_govt_state)
