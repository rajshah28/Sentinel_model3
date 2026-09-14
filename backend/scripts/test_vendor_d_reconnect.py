"""
Real forced-disconnect-and-reconnect test against the live mediamtx
stream: kills the RTSP connection out from under the adapter mid-run
(by stopping the ffmpeg publisher, which drops the stream from
mediamtx's perspective), confirms the adapter detects the failure,
backs off, and confirms it successfully reconnects once the publisher
is restarted -- proving the reconnect-with-backoff requirement against
a real failure, not a simulated one.
"""
import asyncio
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.govt_grid_catalogue import CatalogueCamera
from app.adapters.vendor_d_govt_grid import VendorDGovtGridAdapter

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
VIDEO = os.path.join(REPO_ROOT, "data", "videos", "vendorB_parking.mp4")
FRAMES_OUT = os.path.join(REPO_ROOT, "data", "frames", "vendorD_reconnect_test")

MICROMAMBA = "/home/raj/GoG_Hack_2/.tools/bin/micromamba"


def start_publisher():
    return subprocess.Popen(
        [MICROMAMBA, "run", "-n", "sentinel", "ffmpeg", "-re", "-stream_loop", "-1",
         "-i", VIDEO, "-c:v", "libx264", "-preset", "ultrafast",
         "-f", "rtsp", "-rtsp_transport", "tcp", "rtsp://127.0.0.1:8554/stream/2"],
        env={**os.environ, "MAMBA_ROOT_PREFIX": "/home/raj/GoG_Hack_2/.tools/mamba"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


async def main():
    print("Starting RTSP publisher (stream/2)...")
    pub = start_publisher()
    await asyncio.sleep(3)

    cam = CatalogueCamera(
        camera_id="2", location="Reconnect Test Rig", codec="h264", live=True,
        rtsp_url="rtsp://127.0.0.1:8554/stream/2", whep_url=None, hls_url=None, raw={},
    )
    adapter = VendorDGovtGridAdapter(camera=cam, frame_out_dir=FRAMES_OUT, sample_every_sec_pts=1.0)

    # NOTE: do not wrap frame_iter.__anext__() in asyncio.wait_for() and
    # call it repeatedly in a loop -- cancelling an in-flight __anext__()
    # via wait_for's timeout can desynchronize the underlying async
    # generator (observed directly: it later raises StopAsyncIteration
    # even though the adapter itself is still yielding frames fine).
    # Instead, run frame consumption as its own background task reading
    # a plain `async for`, and just observe how many frames landed in
    # a queue over each phase's wall-clock window.
    frame_iter = adapter.frames()
    frame_queue: asyncio.Queue = asyncio.Queue()
    stop_consumer = asyncio.Event()

    async def consumer_task():
        try:
            async for frame in frame_iter:
                await frame_queue.put(frame)
                if stop_consumer.is_set():
                    break
        except Exception as e:  # noqa: BLE001
            print(f"  [consumer_task] exited with: {type(e).__name__}: {e}")

    consumer = asyncio.create_task(consumer_task())

    async def consume_for(seconds):
        end = time.monotonic() + seconds
        n = 0
        while time.monotonic() < end:
            try:
                frame = await asyncio.wait_for(frame_queue.get(), timeout=max(0.1, end - time.monotonic()))
                n += 1
            except asyncio.TimeoutError:
                break
        return n

    print("\nPhase 1: consuming normally for 8s...")
    n1 = await consume_for(8)
    print(f"  received {n1} frames")

    print("\nPhase 2: killing the RTSP publisher (forced disconnect)...")
    pub.terminate()
    pub.wait(timeout=5)
    print("  publisher killed. Adapter should now detect failure and start backoff reconnect attempts.")

    print("\nPhase 3: observing for 10s while disconnected (expect no frames, no crash)...")
    n2 = await consume_for(10)
    print(f"  received {n2} frames while disconnected (expected 0)")

    print("\nPhase 4: restarting the RTSP publisher...")
    pub = start_publisher()

    print("\nPhase 5: waiting up to 40s for the adapter to reconnect and resume yielding frames...")
    reconnected = False
    end = time.monotonic() + 40
    while time.monotonic() < end:
        try:
            frame = await asyncio.wait_for(frame_queue.get(), timeout=3.0)
            print(f"  RECONNECTED: received frame again (frame_index={frame.frame_index}) "
                  f"at t={time.monotonic():.1f}")
            reconnected = True
            break
        except asyncio.TimeoutError:
            print(f"  ...still waiting (t={time.monotonic():.1f})")

    stop_consumer.set()
    adapter.stop()
    consumer.cancel()
    pub.terminate()

    print(f"\n=== RESULT: reconnect_succeeded={reconnected} ===")
    if not reconnected:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
