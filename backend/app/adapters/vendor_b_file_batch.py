"""
Vendor B adapter: local video file batch reader with a distinct
vendor metadata format (nested JSON-like structure, camelCase keys,
epoch-seconds timestamps) typical of a VMS export/batch-upload tool
rather than a live camera API.

This models a department whose VMS platform doesn't expose a live
protocol at all -- footage arrives as exported batch files with an
accompanying metadata sidecar, which is common with legacy municipal
CCTV systems.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import AsyncIterator

import cv2

from app.adapters.base import VendorAdapter
from app.models.schema import CameraInfo, CameraStatus, NormalizedFrame, VendorProtocol


class VendorBFileBatchAdapter(VendorAdapter):
    vendor_name = "VendorB-CivicGuard-VMS"
    protocol = "file_batch"

    def __init__(
        self,
        camera_id: str,
        department: str,
        location_name: str,
        latitude: float,
        longitude: float,
        video_path: str,
        frame_out_dir: str,
        sample_every_sec: float = 1.5,
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
            protocol=VendorProtocol.FILE_BATCH,
            location_name=self.location_name,
            latitude=self.latitude,
            longitude=self.longitude,
            status=status,
        )

    def _vendor_native_batch_record(self, frame_no: int, img) -> dict:
        """Simulates Vendor B's batch export metadata sidecar format."""
        return {
            "assetType": "frameCapture",
            "sourceFile": os.path.basename(self.video_path),
            "frameSequence": frame_no,
            "capturedAtEpoch": time.time(),
            "resolution": {"w": img.shape[1], "h": img.shape[0]},
        }

    async def frames(self) -> AsyncIterator[NormalizedFrame]:
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"VendorB: could not open batch file {self.video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        sample_every_n_frames = max(1, int(fps * self.sample_every_sec))
        frame_idx = 0

        while True:
            ok, img = cap.read()
            if not ok:
                break

            if frame_idx % sample_every_n_frames == 0:
                record = self._vendor_native_batch_record(frame_idx, img)
                fname = f"{self.camera_id}_{frame_idx:06d}_{uuid.uuid4().hex[:8]}.jpg"
                fpath = os.path.join(self.frame_out_dir, fname)
                cv2.imwrite(fpath, img)

                yield NormalizedFrame(
                    camera_id=self.camera_id,
                    vendor=self.vendor_name,
                    frame_index=frame_idx,
                    width=record["resolution"]["w"],
                    height=record["resolution"]["h"],
                    frame_path=fpath,
                )

            frame_idx += 1

        cap.release()
