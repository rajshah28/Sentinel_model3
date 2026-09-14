import glob
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.anpr.pipeline import detect_and_read_plates

DATA_FRAMES = os.path.join(os.path.dirname(__file__), "..", "..", "data", "frames")


def main():
    for vendor_dir in ("vendorA", "vendorB", "vendorC"):
        frames = sorted(glob.glob(os.path.join(DATA_FRAMES, vendor_dir, "*.jpg")))
        print(f"\n=== {vendor_dir}: {len(frames)} frames ===")
        hits = 0
        t0 = time.time()
        for fp in frames:
            results = detect_and_read_plates(fp, min_conf=0.2)
            if results:
                hits += 1
                for r in results:
                    print(f"  {os.path.basename(fp)}: plate='{r.plate_text}' "
                          f"ocr_conf={r.plate_confidence} det_conf={r.detection_confidence} "
                          f"bbox={r.plate_bbox}")
        elapsed = time.time() - t0
        print(f"  -> {hits}/{len(frames)} frames with a plate read, "
              f"{elapsed:.1f}s total ({elapsed/max(1,len(frames)):.2f}s/frame)")


if __name__ == "__main__":
    main()
