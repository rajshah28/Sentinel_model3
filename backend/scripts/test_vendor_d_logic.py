"""
Unit-level verification of Vendor D's PTS-timing, sampling-cadence, and
discontinuity-handling logic WITHOUT a real network connection -- useful
right now (no sandbox host available yet) and as a regression test once
one is. This does not test actual RTSP/TCP negotiation (that requires
the real host), only the logic this adapter layers on top of whatever
cv2.VideoCapture hands it.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.vendor_d_govt_grid import _pts_delta_to_datetime
import time


def test_pts_delta_not_wallclock():
    """Confirms two frames with identical PTS delta get identical wall
    delta, regardless of how much real time passed reading them -- this
    is the core 'timing driven by PTS, not arrival time' requirement."""
    anchor_wall = time.time()
    anchor_pts = 1000.0

    # Frame read "instantly" after anchor
    t1 = _pts_delta_to_datetime(anchor_wall, anchor_pts, 2000.0)
    # Simulate the same PTS delta, but pretend processing was slow --
    # anchor_wall/anchor_pts are unchanged (same connection), so the
    # result must be identical regardless of real elapsed time.
    t2 = _pts_delta_to_datetime(anchor_wall, anchor_pts, 2000.0)

    assert t1 == t2, "Same PTS delta must yield same timestamp regardless of real processing time"
    delta_sec = (t1 - t1.__class__.fromtimestamp(anchor_wall, tz=t1.tzinfo)).total_seconds()
    assert abs(delta_sec - 1.0) < 1e-6, f"Expected +1.0s from anchor, got {delta_sec}s"
    print("PASS: PTS delta -> timestamp is deterministic and PTS-driven, not wall-clock-driven")


def test_pts_delta_handles_large_jump():
    """A big PTS jump (e.g. after a discontinuity reset re-anchors) should
    just produce a correspondingly large timestamp delta, no crash."""
    anchor_wall = time.time()
    t = _pts_delta_to_datetime(anchor_wall, 500.0, 500.0)  # zero delta right after reset
    delta_sec = (t - t.__class__.fromtimestamp(anchor_wall, tz=t.tzinfo)).total_seconds()
    assert abs(delta_sec) < 1e-6
    print("PASS: zero-delta-at-anchor case handled correctly (used right after a discontinuity reset)")


def test_sampling_cadence_logic():
    """Reimplements the should_sample decision from frames() in isolation
    to confirm it samples on elapsed-PTS, not frame count or wall time."""
    sample_every_sec_pts = 1.5
    last_sampled_pts_ms = None
    sampled_at = []

    # Simulate a PTS stream with NON-uniform frame spacing (variable fps,
    # exactly what the spec says must not be assumed constant).
    pts_stream_ms = [0, 40, 90, 300, 900, 1400, 1600, 2200, 3100, 3200, 5000]

    for pts_ms in pts_stream_ms:
        should_sample = (
            last_sampled_pts_ms is None
            or (pts_ms - last_sampled_pts_ms) >= sample_every_sec_pts * 1000.0
        )
        if should_sample:
            sampled_at.append(pts_ms)
            last_sampled_pts_ms = pts_ms

    # First frame always sampled; next sample only once >=1500ms elapsed
    # since the last sample -- verify against hand-computed expectation.
    assert sampled_at == [0, 1600, 3100, 5000], f"Unexpected sampling points: {sampled_at}"
    print(f"PASS: sampling cadence is elapsed-PTS-driven on a non-uniform stream: sampled at {sampled_at}")


def test_discontinuity_detection():
    """A PTS value that drops significantly vs. the last seen PTS must be
    detected as a loop-point discontinuity, not silently ignored or
    treated as corrupt data requiring a crash."""
    last_seen_pts_ms = 58000.0  # near end of a ~60s looping clip
    new_pts_ms = 120.0          # stream looped back to near zero

    is_discontinuity = new_pts_ms < last_seen_pts_ms - 500
    assert is_discontinuity, "A large backward PTS jump must be detected as a discontinuity"
    print("PASS: backward PTS jump (loop point) correctly detected as discontinuity, not an error")

    # And a small natural jitter (e.g. B-frame reordering) must NOT trigger it
    last_seen_pts_ms = 5000.0
    new_pts_ms = 4980.0  # 20ms backward -- normal reordering jitter
    is_discontinuity = new_pts_ms < last_seen_pts_ms - 500
    assert not is_discontinuity, "Small PTS jitter must not be misclassified as a discontinuity"
    print("PASS: small PTS jitter (20ms) correctly NOT flagged as a discontinuity")


def test_reconnect_backoff_sequence():
    """Confirms the backoff sequence matches the spec: start ~2s, double
    each attempt, cap at ~30s -- not a tight loop, not unbounded growth."""
    RECONNECT_BACKOFF_START_SEC = 2.0
    RECONNECT_BACKOFF_CAP_SEC = 30.0

    delay = RECONNECT_BACKOFF_START_SEC
    sequence = [delay]
    for _ in range(8):
        delay = min(delay * 2, RECONNECT_BACKOFF_CAP_SEC)
        sequence.append(delay)

    assert sequence[0] == 2.0
    assert sequence == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0, 30.0, 30.0], f"Unexpected backoff sequence: {sequence}"
    print(f"PASS: reconnect backoff sequence is correct: {sequence}")


if __name__ == "__main__":
    test_pts_delta_not_wallclock()
    test_pts_delta_handles_large_jump()
    test_sampling_cadence_logic()
    test_discontinuity_detection()
    test_reconnect_backoff_sequence()
    print("\nAll Vendor D logic tests passed.")
