"""
Vendor C adapter: image-sequence / snapshot API poller.

Some departmental systems (especially older DVR/NVR boxes and
low-bandwidth rural deployments) don't expose a stream at all --
they expose a "get current snapshot" HTTP endpoint that a poller
hits on an interval, similar to an MJPEG snapshot API. We simulate
that here by decoding the source video into a sequence of individual
JPEG snapshots on disk up front (the "camera's snapshot buffer"),
then polling that sequence on an interval, exactly as a poller would
hit a real HTTP snapshot endpoint.

Vendor C's native metadata format (simulated): XML-ish flat attributes,
typical of older embedded HTTP camera firmware.
"""
from __future__ import annotations

import glob
import os
import uuid
from typing import AsyncIterator

import cv2

from app.adapters.base import VendorAdapter
from app.models.schema import CameraInfo, CameraStatus, NormalizedFrame, VendorProtocol


class VendorCSnapshotPollAdapter(VendorAdapter):
    vendor_name = "VendorC-SentryEye-DVR"
    protocol = "snapshot_poll"

    def __init__(
        self,
        camera_id: str,
        department: str,
        location_name: str,
        latitude: float,
        longitude: float,
        video_path: str,
        frame_out_dir: str,
        snapshot_buffer_dir: str,
        sample_every_sec: float = 1.0,
    ):
        self.camera_id = camera_id
        self.department = department
        self.location_name = location_name
        self.latitude = latitude
        self.longitude = longitude
        self.video_path = video_path
        self.frame_out_dir = frame_out_dir
        self.snapshot_buffer_dir = snapshot_buffer_dir
        self.sample_every_sec = sample_every_sec
        os.makedirs(self.frame_out_dir, exist_ok=True)
        os.makedirs(self.snapshot_buffer_dir, exist_ok=True)

    def get_camera_info(self) -> CameraInfo:
        status = CameraStatus.ONLINE if os.path.exists(self.video_path) else CameraStatus.OFFLINE
        return CameraInfo(
            camera_id=self.camera_id,
            department=self.department,
            vendor=self.vendor_name,
            protocol=VendorProtocol.SNAPSHOT_POLL,
            location_name=self.location_name,
            latitude=self.latitude,
            longitude=self.longitude,
            status=status,
        )

    def _ensure_snapshot_buffer(self) -> list[str]:
        """Pre-decode the source video into the camera's simulated snapshot buffer."""
        existing = sorted(glob.glob(os.path.join(self.snapshot_buffer_dir, "snap_*.jpg")))
        if existing:
            return existing

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"VendorC: could not open source for snapshot buffer {self.video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        sample_every_n_frames = max(1, int(fps * self.sample_every_sec))
        frame_idx = 0
        paths = []
        while True:
            ok, img = cap.read()
            if not ok:
                break
            if frame_idx % sample_every_n_frames == 0:
                snap_path = os.path.join(self.snapshot_buffer_dir, f"snap_{frame_idx:06d}.jpg")
                cv2.imwrite(snap_path, img)
                paths.append(snap_path)
            frame_idx += 1
        cap.release()
        return paths

    def _vendor_native_snapshot_attrs(self, path: str) -> dict:
        """Simulates Vendor C's XML-ish snapshot attribute response."""
        return {
            "DeviceID": self.camera_id,
            "SnapshotURI": path,
            "Format": "JPEG",
        }

    async def frames(self) -> AsyncIterator[NormalizedFrame]:
        snapshot_paths = self._ensure_snapshot_buffer()

        for i, snap_path in enumerate(snapshot_paths):
            attrs = self._vendor_native_snapshot_attrs(snap_path)
            img = cv2.imread(attrs["SnapshotURI"])
            if img is None:
                continue
            h, w = img.shape[:2]

            fname = f"{self.camera_id}_{i:06d}_{uuid.uuid4().hex[:8]}.jpg"
            fpath = os.path.join(self.frame_out_dir, fname)
            cv2.imwrite(fpath, img)

            yield NormalizedFrame(
                camera_id=self.camera_id,
                vendor=self.vendor_name,
                frame_index=i,
                width=w,
                height=h,
                frame_path=fpath,
            )
