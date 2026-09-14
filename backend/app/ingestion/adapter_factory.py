import os

from app.adapters.govt_grid_catalogue import CatalogueError, fetch_catalogue
from app.adapters.vendor_a_rtsp_sim import VendorARtspSimAdapter
from app.adapters.vendor_b_file_batch import VendorBFileBatchAdapter
from app.adapters.vendor_c_snapshot_poll import VendorCSnapshotPollAdapter
from app.adapters.vendor_d_govt_grid import VendorDGovtGridAdapter
from app.config import FRAMES_DIR, GOVT_GRID_HOST, VENDOR_SOURCES, VIDEOS_DIR


def build_demo_adapters():
    """Builds the adapter instances for every source that has demo footage attached."""
    adapters = []
    for src in VENDOR_SOURCES:
        if src["kind"] == "A":
            adapters.append(VendorARtspSimAdapter(
                camera_id=src["camera_id"], department=src["department"],
                location_name=src["location_name"], latitude=src["latitude"], longitude=src["longitude"],
                video_path=os.path.join(VIDEOS_DIR, src["video_file"]),
                frame_out_dir=os.path.join(FRAMES_DIR, "vendorA"),
                sample_every_sec=src["sample_every_sec"],
            ))
        elif src["kind"] == "B":
            adapters.append(VendorBFileBatchAdapter(
                camera_id=src["camera_id"], department=src["department"],
                location_name=src["location_name"], latitude=src["latitude"], longitude=src["longitude"],
                video_path=os.path.join(VIDEOS_DIR, src["video_file"]),
                frame_out_dir=os.path.join(FRAMES_DIR, "vendorB"),
                sample_every_sec=src["sample_every_sec"],
            ))
        elif src["kind"] == "C":
            adapters.append(VendorCSnapshotPollAdapter(
                camera_id=src["camera_id"], department=src["department"],
                location_name=src["location_name"], latitude=src["latitude"], longitude=src["longitude"],
                video_path=os.path.join(VIDEOS_DIR, src["video_file"]),
                frame_out_dir=os.path.join(FRAMES_DIR, "vendorC"),
                snapshot_buffer_dir=os.path.join(FRAMES_DIR, "vendorC_buffer"),
                sample_every_sec=src["sample_every_sec"],
            ))
    return adapters


def build_govt_grid_adapters(sample_every_sec_pts: float = 1.5):
    """
    Fetches the live catalogue from the configured government sandbox
    host and builds one VendorDGovtGridAdapter per camera it lists.
    Raises CatalogueError if the host isn't configured or unreachable --
    callers must surface that clearly rather than silently falling back
    to a simulated source, since Demo 4 specifically requires a real
    live feed.
    """
    if not GOVT_GRID_HOST:
        raise CatalogueError(
            "SENTINEL_GOVT_GRID_HOST is not set. The government grid host "
            "must be supplied explicitly by the operator (never inferred) "
            "before this adapter can be built."
        )
    cameras = fetch_catalogue(GOVT_GRID_HOST)
    frame_out_dir = os.path.join(FRAMES_DIR, "vendorD_govt")
    return [
        VendorDGovtGridAdapter(
            camera=cam,
            frame_out_dir=frame_out_dir,
            sample_every_sec_pts=sample_every_sec_pts,
        )
        for cam in cameras
    ]
