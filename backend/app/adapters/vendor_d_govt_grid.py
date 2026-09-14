"""
Vendor D adapter: the government-provided live CCTV sandbox grid.

Unlike vendors A/B/C (which read finite local video files as a stand-in
for their respective ingestion mechanics), this adapter connects to a
genuinely live RTSP source over the network, with no seeking and no
end-of-stream in the normal case. It implements the same VendorAdapter
interface as the other three -- get_camera_info() / frames() -- so
nothing downstream (ANPR pipeline, bus, correlation engine, API) needs
to know this source is live rather than a recorded file.

Built strictly to the integration reference supplied directly by the
user in this session (RTSP/WHEP/HLS catalogue-driven grid, PTS timing,
reconnect-with-backoff, resilience requirements). See the do's/don'ts
in the class docstring below for how each requirement maps to code here.

SECURITY / PROVENANCE NOTE: the host this adapter connects to
(SENTINEL_GOVT_GRID_HOST) must be supplied explicitly by the user as
plain configuration. This module does not fetch, infer, or accept a
host value from any tool result, file, or other in-band content --
only from environment configuration set by the operator.

CREDENTIALS: RTSP/WHEP URLs on this grid embed an email + password
(rtsp://email:password@host:port/...). self.camera.rtsp_url therefore
contains a live secret. Every log line that could include it MUST go
through govt_grid_catalogue.redact_url() first -- see every logger.*
call below that touches self.camera.rtsp_url. Never pass the raw URL
to logger.info/warning/error directly.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import AsyncIterator, Optional

import cv2

from app.adapters.base import VendorAdapter
from app.adapters.govt_grid_catalogue import CatalogueCamera, CatalogueError, fetch_catalogue, redact_url
from app.models.schema import CameraInfo, CameraStatus, NormalizedFrame, VendorProtocol

logger = logging.getLogger("sentinel.adapters.govt_grid")

# DO: force RTSP over TCP -- UDP fails across NAT/firewalls and produces
# corrupt frames that look like model bugs.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

RECONNECT_BACKOFF_START_SEC = 2.0
RECONNECT_BACKOFF_CAP_SEC = 30.0


class VendorDGovtGridAdapter(VendorAdapter):
    """
    Live RTSP adapter for the government sandbox grid.

    Requirement -> implementation mapping:
      - "force RTSP over TCP"            -> OPENCV_FFMPEG_CAPTURE_OPTIONS set
                                             module-wide + CAP_FFMPEG backend
      - "don't trust reported frame rate" -> fps is never read from the
                                             capture; sampling is driven by
                                             elapsed PTS only
      - "drive timing from PTS"          -> every NormalizedFrame.timestamp
                                             is derived from
                                             CAP_PROP_POS_MSEC, not
                                             datetime.now()
      - "don't assume constant frame rate" -> the read loop has no fixed
                                             per-frame sleep/assumption;
                                             it reacts to whatever PTS
                                             delta actually occurs
      - "reconnect with exponential backoff" -> _connect_with_backoff()
      - "decoder warnings at join aren't fatal" -> only a sustained run
                                             of failed .read() calls
                                             triggers reconnect logic;
                                             OpenCV/ffmpeg's own stderr
                                             warnings are not treated as
                                             python exceptions
      - "mixed codec grid"               -> codec is never branched on;
                                             cv2.VideoCapture(..., CAP_FFMPEG)
                                             handles H.264/H.265 uniformly
      - "no fixed-shape batch"           -> each camera has its own
                                             adapter instance with its own
                                             sampling cadence based on its
                                             own PTS stream
      - "scene discontinuity is normal"  -> a large backward jump in PTS
                                             is logged and treated as a
                                             loop point, not an error;
                                             downstream correlation-engine
                                             dedup state ages out on its
                                             own 10s window (see
                                             app/correlation/engine.py)
                                             rather than assuming infinite
                                             continuity
      - "no file download / live capture only" -> this adapter only ever
                                             opens the rtsp:// URL from
                                             the catalogue, never
                                             /stream/<id> HTTP fallback
      - "pace load: only open cameras being processed" -> frames() is a
                                             generator; the capture is
                                             opened on first iteration
                                             and released in a finally
                                             block, not held open by
                                             construction
    """

    vendor_name = "VendorD-GovtSandboxGrid"
    protocol = "rtsp_live"

    def __init__(
        self,
        camera: CatalogueCamera,
        department: str = "State Home Department (Govt Sandbox Grid)",
        latitude: float = 23.0225,   # Gandhinagar/Ahmedabad area placeholder;
        longitude: float = 72.5714,  # catalogue does not provide lat/long.
        frame_out_dir: str = "",
        sample_every_sec_pts: float = 1.5,
        max_consecutive_read_failures: int = 15,
    ):
        self.camera = camera
        self.camera_id = f"CAM-GOVT-{camera.camera_id}"
        self.department = department
        self.latitude = latitude
        self.longitude = longitude
        self.frame_out_dir = frame_out_dir
        self.sample_every_sec_pts = sample_every_sec_pts
        self.max_consecutive_read_failures = max_consecutive_read_failures
        os.makedirs(self.frame_out_dir, exist_ok=True)

        self._stop = False

    def get_camera_info(self) -> CameraInfo:
        return CameraInfo(
            camera_id=self.camera_id,
            department=self.department,
            vendor=self.vendor_name,
            protocol=VendorProtocol.RTSP_STREAM,
            location_name=f"Govt Grid: {self.camera.location}",
            latitude=self.latitude,
            longitude=self.longitude,
            status=CameraStatus.ONLINE if self.camera.live else CameraStatus.OFFLINE,
        )

    def stop(self):
        """Signal the frames() loop to exit cleanly (e.g. on app shutdown)."""
        self._stop = True

    def _open_capture_blocking(self) -> cv2.VideoCapture:
        # CAP_PROP_OPEN_TIMEOUT_MSEC / CAP_PROP_READ_TIMEOUT_MSEC are set
        # too (harmless, and effective on some backends/builds), but they
        # are NOT sufficient on their own: tested directly against a real
        # "black hole" port (TCP accepts the connection, then never
        # responds -- a realistic network failure mode, distinct from an
        # actively-refused port which fails in <1s regardless), this
        # in-process call still hung past 20s even with both properties
        # set to 8000ms. The FFmpeg backend does not reliably honor these
        # properties in this OpenCV/ffmpeg build. Ownership of the actual
        # bound therefore belongs to the caller, which wraps this call in
        # asyncio.wait_for() -- see _connect_with_backoff().
        cap = cv2.VideoCapture()
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000)
        cap.open(self.camera.rtsp_url, cv2.CAP_FFMPEG)
        return cap

    async def _open_capture(self, timeout_sec: float = 8.0) -> cv2.VideoCapture:
        """
        Runs the blocking cv2 open call in a thread pool executor and
        enforces the real timeout via asyncio.wait_for -- see
        _open_capture_blocking()'s docstring for why OpenCV's own
        timeout properties can't be trusted alone. On timeout, the
        worker thread may continue running in the background (there is
        no clean way to cancel a blocking C call from Python); we
        release the capture object we got back and let that thread's
        eventual completion be a no-op for anything that matters, since
        we've already moved on to the next reconnect attempt.
        """
        loop = asyncio.get_event_loop()
        try:
            cap = await asyncio.wait_for(
                loop.run_in_executor(None, self._open_capture_blocking),
                timeout=timeout_sec,
            )
            return cap
        except asyncio.TimeoutError:
            logger.warning(
                "VendorD %s: connect attempt timed out after %.1fs (host unreachable "
                "or not responding -- this is the 'black hole' failure mode, distinct "
                "from an actively-refused connection)",
                self.camera_id, timeout_sec,
            )
            # Return a never-opened capture so the caller's isOpened() check
            # uniformly treats this the same as any other failed attempt.
            return cv2.VideoCapture()

    async def _connect_with_backoff(self) -> cv2.VideoCapture:
        """
        DO: reconnect automatically, with exponential backoff starting at
        ~2s and capped at ~30s -- not a tight loop.
        """
        delay = RECONNECT_BACKOFF_START_SEC
        attempt = 0
        while not self._stop:
            attempt += 1
            logger.info("VendorD %s: connecting (attempt %d) to %s",
                        self.camera_id, attempt, redact_url(self.camera.rtsp_url))
            cap = await self._open_capture()
            if cap.isOpened():
                logger.info("VendorD %s: connected", self.camera_id)
                return cap
            cap.release()
            logger.warning(
                "VendorD %s: connect attempt %d failed, retrying in %.1fs",
                self.camera_id, attempt, delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_BACKOFF_CAP_SEC)
        raise RuntimeError(f"VendorD {self.camera_id}: stopped before connecting")

    async def frames(self) -> AsyncIterator[NormalizedFrame]:
        cap = await self._connect_with_backoff()
        last_sampled_pts_ms: Optional[float] = None
        last_seen_pts_ms: Optional[float] = None
        # Anchor: wall-clock time + PTS value at the moment of the first
        # frame read after (re)connecting. Every subsequent timestamp is
        # this anchor plus (current_pts - anchor_pts) -- i.e. driven by
        # the PTS *delta*, never by when our own code happened to read the
        # frame. Reset on every reconnect and every detected discontinuity,
        # since PTS is only meaningful relative to a given stream session.
        pts_anchor_wall: Optional[float] = None
        pts_anchor_pts_ms: Optional[float] = None
        consecutive_failures = 0
        frame_idx = 0

        try:
            while not self._stop:
                # Reads are blocking (OpenCV/ffmpeg); run off the event loop
                # so this adapter doesn't stall the rest of the federation.
                ok, img = await asyncio.get_event_loop().run_in_executor(None, cap.read)

                if not ok or img is None:
                    consecutive_failures += 1
                    logger.debug("VendorD %s: read failed (%d consecutive)",
                                 self.camera_id, consecutive_failures)
                    # DON'T treat decoder warnings / occasional failed reads
                    # at join as fatal -- only reconnect after a sustained
                    # run of failures, which indicates a real disconnect.
                    if consecutive_failures >= self.max_consecutive_read_failures:
                        logger.warning(
                            "VendorD %s: %d consecutive read failures, reconnecting",
                            self.camera_id, consecutive_failures,
                        )
                        cap.release()
                        cap = await self._connect_with_backoff()
                        consecutive_failures = 0
                        last_sampled_pts_ms = None
                        last_seen_pts_ms = None
                        pts_anchor_wall = None
                        pts_anchor_pts_ms = None
                    else:
                        await asyncio.sleep(0.1)
                    continue

                consecutive_failures = 0

                # DO: drive all timing from PTS, never wall-clock arrival time.
                pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

                # DO: expect a scene discontinuity at the loop point --
                # a PTS value that goes backwards (or resets near zero)
                # means the recording looped, not that anything is broken.
                # Long-lived state should recover, not assume infinite
                # continuity: we just reset our own sampling clock here;
                # the correlation engine's dedup state ages out on its own
                # 10-second window regardless (app/correlation/engine.py),
                # so a hard cut can't produce a stale false-dedup either.
                if last_seen_pts_ms is not None and pts_ms < last_seen_pts_ms - 500:
                    logger.info(
                        "VendorD %s: PTS went backwards (%.0fms -> %.0fms) -- "
                        "scene discontinuity / loop point, not an error. "
                        "Resetting sampling clock.",
                        self.camera_id, last_seen_pts_ms, pts_ms,
                    )
                    last_sampled_pts_ms = None
                    pts_anchor_wall = None
                    pts_anchor_pts_ms = None
                last_seen_pts_ms = pts_ms

                if pts_anchor_wall is None:
                    pts_anchor_wall = time.time()
                    pts_anchor_pts_ms = pts_ms

                # DON'T assume constant frame rate / don't trust CAP_PROP_FPS:
                # sample based on actual elapsed PTS since the last sampled
                # frame, not a fixed frame-count stride.
                should_sample = (
                    last_sampled_pts_ms is None
                    or (pts_ms - last_sampled_pts_ms) >= self.sample_every_sec_pts * 1000.0
                )

                if should_sample:
                    h, w = img.shape[:2]
                    fname = f"{self.camera_id}_{frame_idx:08d}_{uuid.uuid4().hex[:8]}.jpg"
                    fpath = os.path.join(self.frame_out_dir, fname)
                    cv2.imwrite(fpath, img)

                    yield NormalizedFrame(
                        camera_id=self.camera_id,
                        vendor=self.vendor_name,
                        frame_index=frame_idx,
                        # PTS-derived timestamp: anchor wall-clock + PTS delta
                        # since the anchor, never raw arrival time. This is
                        # what makes the trace-timeline timestamps accurate
                        # per the integration spec's PTS-timing requirement.
                        timestamp=_pts_delta_to_datetime(pts_anchor_wall, pts_anchor_pts_ms, pts_ms),
                        width=w,
                        height=h,
                        frame_path=fpath,
                    )
                    last_sampled_pts_ms = pts_ms
                    frame_idx += 1
        finally:
            cap.release()
            logger.info("VendorD %s: capture released", self.camera_id)


def _pts_delta_to_datetime(anchor_wall: float, anchor_pts_ms: float, pts_ms: float):
    """
    RTSP PTS is a stream-relative clock, not wall-clock, and there is no
    way to convert a bare PTS value into an absolute timestamp on its
    own. What the integration spec actually requires is that *timing
    logic* (sampling cadence, inter-frame deltas, anything a tracker
    would use) is driven by PTS deltas, not by wall-clock arrival time --
    arrival time is skewed by buffered-GOP replay on join and by our own
    processing jitter, PTS is not.

    So: we anchor once (wall-clock `time.time()` + the PTS value seen at
    that same instant, captured right after connecting or after a
    discontinuity reset -- see frames()), and every subsequent frame's
    absolute timestamp is anchor_wall + (pts_ms - anchor_pts_ms) / 1000.
    The delta term is 100% PTS-derived; wall-clock only supplies the
    single fixed offset needed to express an absolute, sortable
    timestamp for the trace API/UI, exactly once per connection.
    """
    from datetime import datetime, timedelta, timezone
    delta_sec = (pts_ms - anchor_pts_ms) / 1000.0
    return datetime.fromtimestamp(anchor_wall, tz=timezone.utc) + timedelta(seconds=delta_sec)
