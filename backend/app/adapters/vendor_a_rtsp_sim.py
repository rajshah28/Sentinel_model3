"""
Vendor A adapter: simulates an RTSP-style continuous stream reader.

Real departmental VMS platforms that expose RTSP/ONVIF streams would be
read here with cv2.VideoCapture("rtsp://..."). For the demo we point
OpenCV's VideoCapture at a recorded highway traffic file and read it
frame-by-frame exactly as we would a live RTSP socket, sampling every
N seconds of footage rather than every frame (CPU-only inference budget).

Vendor A's native metadata format (simulated): a flat dict with short
keys, typical of embedded-device firmware APIs.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import AsyncIterator

import cv2

from app.adapters.base import VendorAdapter
from app.models.schema import CameraInfo, CameraStatus, NormalizedFrame, VendorProtocol


class VendorARtspSimAdapter(VendorAdapter):
    vendor_name = "VendorA-Streamline-VMS"
    protocol = "rtsp_stream"

    def __init__(
        self,
        camera_id: str,
        department: str,
        location_name: str,
        latitude: float,
        longitude: float,
        video_path: str,
        frame_out_dir: str,
        sample_every_sec: float = 2.0,
    ):
        self.camera_id = camera_id
        self.department = department
        self.location_name = location_name
        self.latitude = latitude
        self.longitude = longitude
        self.video_path = video_path
        self.frame_out_dir = frame_out_dir
        self.sample_every_sec = sample_every_sec
        os.makedirs(self.frame_out_dir, exist_ok=True)

    def get_camera_info(self) -> CameraInfo:
        status = CameraStatus.ONLINE if os.path.exists(self.video_path) else CameraStatus.OFFLINE
        return CameraInfo(
            camera_id=self.camera_id,
            department=self.department,
            vendor=self.vendor_name,
            protocol=VendorProtocol.RTSP_STREAM,
            location_name=self.location_name,
            latitude=self.latitude,
            longitude=self.longitude,
            status=status,
        )

    def _vendor_native_read(self, cap: cv2.VideoCapture) -> dict | None:
        """Simulates Vendor A's native firmware response shape for one frame read."""
        ok, frame = cap.read()
        if not ok:
            return None
        return {"ok": 1, "img": frame, "ts_ms": cap.get(cv2.CAP_PROP_POS_MSEC)}

    async def frames(self) -> AsyncIterator[NormalizedFrame]:
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"VendorA: could not open stream source {self.video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        sample_every_n_frames = max(1, int(fps * self.sample_every_sec))
        frame_idx = 0
        emitted = 0

        while True:
            native = self._vendor_native_read(cap)
            if native is None:
                break

            if frame_idx % sample_every_n_frames == 0:
                img = native["img"]
                h, w = img.shape[:2]
                fname = f"{self.camera_id}_{frame_idx:06d}_{uuid.uuid4().hex[:8]}.jpg"
                fpath = os.path.join(self.frame_out_dir, fname)
                cv2.imwrite(fpath, img)

                yield NormalizedFrame(
                    camera_id=self.camera_id,
                    vendor=self.vendor_name,
                    frame_index=frame_idx,
                    width=w,
                    height=h,
                    frame_path=fpath,
                )
                emitted += 1

            frame_idx += 1

        cap.release()
