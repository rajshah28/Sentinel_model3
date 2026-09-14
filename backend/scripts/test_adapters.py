import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.vendor_a_rtsp_sim import VendorARtspSimAdapter
from app.adapters.vendor_b_file_batch import VendorBFileBatchAdapter
from app.adapters.vendor_c_snapshot_poll import VendorCSnapshotPollAdapter

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data")


async def main():
    a = VendorARtspSimAdapter(
        camera_id="CAM-VLS-01", department="Valsad Traffic Police",
        location_name="NH48 Valsad Bypass", latitude=20.5992, longitude=72.9342,
        video_path=os.path.join(DATA, "videos", "vendorA_highway.mp4"),
        frame_out_dir=os.path.join(DATA, "frames", "vendorA"),
        sample_every_sec=2.0,
    )
    b = VendorBFileBatchAdapter(
        camera_id="CAM-DHD-01", department="Dahod City Police",
        location_name="Dahod Bus Stand Parking", latitude=22.8333, longitude=74.2667,
        video_path=os.path.join(DATA, "videos", "vendorB_parking.mp4"),
        frame_out_dir=os.path.join(DATA, "frames", "vendorB"),
        sample_every_sec=1.0,
    )
    c = VendorCSnapshotPollAdapter(
        camera_id="CAM-SOM-01", department="Somnath Traffic Police",
        location_name="Somnath Temple Road Junction", latitude=20.8880, longitude=70.4013,
        video_path=os.path.join(DATA, "videos", "vendorC_closeup.mp4"),
        frame_out_dir=os.path.join(DATA, "frames", "vendorC"),
        snapshot_buffer_dir=os.path.join(DATA, "frames", "vendorC_buffer"),
        sample_every_sec=1.0,
    )

    for adapter in (a, b, c):
        info = adapter.get_camera_info()
        print(f"\n=== {adapter.vendor_name} ({adapter.protocol}) ===")
        print("camera_info:", info.model_dump())
        count = 0
        async for frame in adapter.frames():
            count += 1
            if count <= 2:
                print("frame:", frame.model_dump())
        print(f"total frames emitted: {count}")


if __name__ == "__main__":
    asyncio.run(main())
