"""
Real end-to-end test of VendorDGovtGridAdapter against a genuinely live
RTSP stream (mediamtx serving looped demo footage at
rtsp://127.0.0.1:8554/stream/1 -- structurally identical to the real
sandbox grid: real TCP RTSP, real H.264/RTP, real PTS, continuously
looping). Not a mock: this drives the actual production adapter code
path (frames(), PTS-based sampling, discontinuity detection at the loop
point) against a real network stream.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.govt_grid_catalogue import CatalogueCamera
from app.adapters.vendor_d_govt_grid import VendorDGovtGridAdapter
from app.anpr.pipeline import detect_and_read_plates

FRAMES_OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "frames", "vendorD_govt_test")


async def main():
    cam = CatalogueCamera(
        camera_id="1",
        location="Test Rig (mediamtx, real RTSP, looped demo footage)",
        codec="h264",
        live=True,
        rtsp_url="rtsp://127.0.0.1:8554/stream/1",
        whep_url="http://127.0.0.1:8889/stream/1/whep",
        hls_url="http://127.0.0.1:8888/stream/1/index.m3u8",
        raw={},
    )
    adapter = VendorDGovtGridAdapter(
        camera=cam,
        frame_out_dir=FRAMES_OUT,
        sample_every_sec_pts=1.0,
    )

    info = adapter.get_camera_info()
    print(f"camera_info: {info.model_dump()}")

    print("\nRunning frames() for ~15 real seconds, sampling every 1.0s of PTS...")
    count = 0
    start = time.monotonic()
    detections_found = 0

    async for frame in adapter.frames():
        count += 1
        print(f"  sampled frame {count}: camera_id={frame.camera_id} "
              f"pts_derived_ts={frame.timestamp.isoformat()} "
              f"size={frame.width}x{frame.height} path={os.path.basename(frame.frame_path)}")

        results = detect_and_read_plates(frame.frame_path, min_conf=0.2)
        for r in results:
            detections_found += 1
            print(f"    -> PLATE DETECTED: '{r.plate_text}' "
                  f"ocr_conf={r.plate_confidence} det_conf={r.detection_confidence}")

        if time.monotonic() - start > 15:
            adapter.stop()
            break

    print(f"\nTotal sampled frames: {count}, total plate detections: {detections_found}")


if __name__ == "__main__":
    asyncio.run(main())
