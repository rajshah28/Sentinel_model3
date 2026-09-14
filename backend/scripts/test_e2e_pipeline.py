"""
End-to-end pipeline test: real adapters -> real ANPR -> real bus ->
real correlation engine -> real Postgres. Prints every alert fired.
This is the Phase 3+4 verification gate.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.vendor_a_rtsp_sim import VendorARtspSimAdapter
from app.adapters.vendor_b_file_batch import VendorBFileBatchAdapter
from app.adapters.vendor_c_snapshot_poll import VendorCSnapshotPollAdapter
from app.bus.event_bus import Topics, bus
from app.correlation.engine import engine
from app.ingestion.orchestrator import ingest_adapter

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data")


async def alert_drain(queue):
    async for alert in bus.drain(Topics.ALERTS, queue):
        print(f"\n*** ALERT FIRED *** plate={alert.plate_text} camera={alert.camera_id} "
              f"department={alert.department} reason='{alert.reason}' "
              f"confidence={alert.confidence} timestamp={alert.timestamp}")


async def main():
    # Register the alert listener's queue synchronously before publishing anything.
    alert_queue = bus.subscribe_now(Topics.ALERTS)
    listener_task = asyncio.create_task(alert_drain(alert_queue))
    correlation_task = engine.start()

    adapters = [
        VendorARtspSimAdapter(
            camera_id="CAM-VLS-01", department="Valsad Traffic Police",
            location_name="NH48 Valsad Bypass", latitude=20.5992, longitude=72.9342,
            video_path=os.path.join(DATA, "videos", "vendorA_highway.mp4"),
            frame_out_dir=os.path.join(DATA, "frames", "vendorA"),
            sample_every_sec=2.0,
        ),
        VendorBFileBatchAdapter(
            camera_id="CAM-DHD-01", department="Dahod City Police",
            location_name="Dahod Bus Stand Parking", latitude=22.8333, longitude=74.2667,
            video_path=os.path.join(DATA, "videos", "vendorB_parking.mp4"),
            frame_out_dir=os.path.join(DATA, "frames", "vendorB"),
            sample_every_sec=1.0,
        ),
        VendorCSnapshotPollAdapter(
            camera_id="CAM-SOM-01", department="Somnath Traffic Police",
            location_name="Somnath Temple Road Junction", latitude=20.8880, longitude=70.4013,
            video_path=os.path.join(DATA, "videos", "vendorC_closeup.mp4"),
            frame_out_dir=os.path.join(DATA, "frames", "vendorC"),
            snapshot_buffer_dir=os.path.join(DATA, "frames", "vendorC_buffer"),
            sample_every_sec=1.0,
        ),
    ]

    total = 0
    for adapter in adapters:
        print(f"\n--- ingesting {adapter.vendor_name} ({adapter.camera_id}) ---")
        n = await ingest_adapter(adapter, min_conf=0.2)
        print(f"emitted {n} detection events")
        total += n

    # give the correlation engine a moment to drain the queue
    await asyncio.sleep(1.0)

    print(f"\n=== TOTAL detection events emitted: {total} ===")
    correlation_task.cancel()
    listener_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
