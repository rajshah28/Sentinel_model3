"""
Quick reachability probe: tries connecting to each fallback camera id
with a short timeout, reports which ones actually respond, without
running the full ANPR pipeline on any of them. Use this to find a
reachable camera id fast, rather than waiting through a full-duration
capture sweep of all 30 ids sequentially.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.govt_grid_catalogue import fetch_catalogue, redact_url
from app.config import GOVT_GRID_HOST


async def probe_one(camera, timeout_sec=6.0):
    import cv2
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

    def _open():
        cap = cv2.VideoCapture()
        cap.open(camera.rtsp_url, cv2.CAP_FFMPEG)
        return cap

    loop = asyncio.get_event_loop()
    t0 = time.time()
    try:
        cap = await asyncio.wait_for(loop.run_in_executor(None, _open), timeout=timeout_sec)
    except asyncio.TimeoutError:
        return camera.camera_id, False, timeout_sec, None

    elapsed = time.time() - t0
    if not cap.isOpened():
        cap.release()
        return camera.camera_id, False, elapsed, None

    ok, frame = cap.read()
    shape = frame.shape if ok else None
    cap.release()
    return camera.camera_id, ok, elapsed, shape


async def main():
    cameras = fetch_catalogue(GOVT_GRID_HOST)
    print(f"Probing {len(cameras)} camera(s) from {GOVT_GRID_HOST}, {6.0}s timeout each...\n")

    reachable = []
    for cam in cameras:
        cam_id, ok, elapsed, shape = await probe_one(cam)
        status = f"OK shape={shape}" if ok else "unreachable/no frame"
        print(f"  {cam_id}: {status} ({elapsed:.1f}s)")
        if ok:
            reachable.append(cam_id)

    print(f"\n{len(reachable)}/{len(cameras)} reachable: {reachable}")


if __name__ == "__main__":
    asyncio.run(main())
