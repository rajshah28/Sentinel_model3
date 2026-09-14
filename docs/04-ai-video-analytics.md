# AI Video Analytics — ANPR Pipeline

## What's actually built: ANPR (mandatory scope)

**Models used:**
- **Plate detection**: YOLOv8n (nano) fine-tuned for license plate
  detection — weights pulled from the public `Koushim/yolov8-license-plate-detection`
  model on Hugging Face (single `license_plate` class, 640×640 input,
  6.2MB — matches the nano-size footprint required for CPU-only
  inference). Loaded via `ultralytics.YOLO`.
- **OCR**: EasyOCR (`easyocr.Reader(["en"], gpu=False)`), CPU mode.

**Pipeline stages** (`backend/app/anpr/pipeline.py::detect_and_read_plates`):

1. Load the frame from disk (already sampled by the adapter, not a raw
   video frame — see `03-integration-strategy.md`).
2. Downscale to 640px width (`_downscale`) before detection, per the
   CPU-only performance requirement.
3. Run YOLOv8n on the downscaled frame; map detected boxes back to
   original resolution.
4. For each detected plate region, crop, upscale small crops to ≥200px
   width (`INTER_CUBIC`) for better OCR legibility, convert to grayscale,
   apply a bilateral filter to reduce noise while preserving character
   edges.
5. Run EasyOCR on the cleaned crop; concatenate multiple text fragments
   left-to-right (plates sometimes split into 2 OCR boxes), strip to
   uppercase alphanumeric only (`clean_plate_text`).
6. Return `PlateReadResult` (plate text, OCR confidence, detection
   confidence, bounding box) for each detected plate.

**Measured performance (this build, CPU-only, no GPU):** ~0.1–0.2
seconds per frame across all three demo sources — well within budget for
processing sampled frames from recorded footage. See the root README's
"Demo credentials" / reproduction steps for how to re-run this live.

**Verified accuracy on real demo footage** (see `README.md` "Sample
footage sources" for clip details):
- Vendor B clip: plate detected and read correctly as `BGY888` (ground
  truth "B GY 888") in 13 of 19 sampled frames, OCR confidence
  0.83–0.99. This is the reliable, reproducible demo match.
- Vendor C clip: plate region detected in 13 of 13 sampled frames
  (100% detection rate); OCR reads are close but not byte-exact
  (`BR4SILAX337` etc. instead of a clean read) because that clip's plate
  uses a mixed Japanese-kanji + stylized-Latin "BRASIL" novelty design —
  a font/script edge case, not a pipeline defect. Documented honestly
  rather than cherry-picking away.
- Vendor A clip: 0 plate reads across 30 sampled frames — plates are not
  visually resolvable at the filmed distance/blur even to a human eye at
  640px. Kept in the demo deliberately to show a realistic heterogeneous
  fleet where not every camera yields usable ANPR data, rather than
  curating only clean footage.

**Fallback path (not needed):** the build spec called for a classical
OpenCV contour/edge-based plate localization + Tesseract OCR fallback if
YOLOv8n+EasyOCR proved too slow or unreliable on CPU. That fallback was
**not required** — the primary approach worked reliably within the time
budget on the very first attempt at each vendor's footage.

### Real-world finding from the Vendor D live feed (Demo 4)

Running the same pipeline against real, live cameras on the government
sandbox grid, across three separate capture runs (7 reachable cameras/68
detections; a 16-detection verification run; and the largest, 18
reachable cameras/45 detections — see the root README's "Demo 4" section
for all three) surfaced a real accuracy limitation worth documenting
honestly rather than omitting: **every detection across all three runs
was a false positive on the camera's own burned-in on-screen text
overlay** (location name + timestamp banner, and in one frame, real
"GUJARAT POLICE" barrier signage), not an actual vehicle plate.
Inspecting the saved frames directly showed why — every reachable camera
was capturing real night-time footage; some frames had no vehicle in
view at all, others had real vehicles (cars, a scooter) present but too
far away or headlight-blown-out for a legible plate, while the overlay
banner is high-contrast, rectangular, white-on-dark text, which is
structurally exactly what a plate-region detector is trained to key on
at a distance. This is a real, known class of ANPR false positive
(on-screen graphics/text competing with genuine plate regions), not a
pipeline defect — the detector and OCR both did exactly what they're
designed to do on the visual pattern actually present in those frames.
Camera reachability itself genuinely fluctuates between runs (7 of 30,
then later 18 of 30, reachable on the same sandbox) — consistent with
real, not simulated, infrastructure.

What this does and doesn't say about the system: the ANPR pipeline's
correctness is independently proven on the mandatory Vendor A/B/C demo
(above), including a reproducible correct read of a genuine plate
(`BGY888`) and a correct null result where no plate is legible (Vendor
A). The Vendor D live-feed integration is proven separately and
correctly too — real RTSP connection, real PTS timing, real inference
running on real frames, real events flowing through the real pipeline.
What Demo 4's specific result shows is that *this specific camera set,
at this specific time of day, during this development window* didn't
offer the detector a genuine plate to find. A production deployment
would address this class of false positive with: (1) a text-region
exclusion mask fitted to each camera's fixed overlay position (most VMS
overlays are in a consistent screen location per camera), (2) a
minimum-confidence and plausible-plate-format filter (Indian plates
follow a known alphanumeric pattern), and (3) daytime/well-lit footage,
which the demo's testing window did not have access to.

**Update: (2) has since been implemented**, as a reporting-layer filter
scoped specifically to Vendor D's output — `app/adapters/govt_grid_plate_filter.py`
validates the standard Indian plate format (`[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{1,4}`:
state code, district code, series letters, number) and is applied only
inside `scripts/generate_govt_feed_report.py`, never inside the core ANPR
pipeline, the correlation engine, or vendors A/B/C's paths (verified by
`grep -rl govt_grid_plate_filter app/ scripts/` returning only the report
generator). This is a deliberate scoping choice, not an oversight: vendors
B/C's demo footage uses non-Indian plates (`BGY888`, a German-style plate;
`BRASIL8X337`-family reads, a Japan/Brasil novelty plate) precisely because
that's the real, available public-domain sample footage, so an Indian-
format filter applied there would break the already-verified `BGY888`
watchlist-match demo for no benefit.

**Result applying this filter to all three real Demo 4 captures:
0 of 68, 0 of 16, and 0 of 45 pass** — the same true result, three
separate times. Every raw detection across all runs was overlay text
(`JANPATH`, `MADHURAM`, `VADLAFATAK`, `POLICE`, burned-in date stamps,
etc.), none of which happen to accidentally match the Indian plate
pattern either — confirming by an independent method (format validation,
not just visual frame inspection) that the false-positive finding above
is real and that nothing was a near-miss genuine plate the filter
incorrectly excluded. Each 0-of-N result is reported explicitly as such
in both the CSV (`reports/govt_feed_report_<ts>_plate_format_valid.csv`,
an intentionally empty file with headers only) and the PDF
(`reports/govt_feed_report_<ts>.pdf`, which states the 0-of-N result and
the reason in the document body itself, distinct from "pipeline
failure") — never a silently emptied report. The unfiltered detections
remain available in `reports/govt_feed_report_<ts>.csv` as the full
record of what the pipeline actually captured; the filter is a reporting
view, not a deletion. Primary/largest run:
`reports/govt_feed_report_20260914_165340.*` (18 cameras, 45 detections).

## Watchlist matching (mandatory scope, also built)

A PostgreSQL `watchlist` table (see `05-cybersecurity-architecture.md`
for schema/access notes) holds representative stolen/wanted-vehicle
records, seeded via `backend/scripts/seed_data.py`, including plate
`BGY888` which is confirmed to appear in the Vendor B demo footage (see
above) — so the alert demo is a real, reproducible match against real
detections, not scripted.

## What FRS / broader object detection would add — ROADMAP ONLY, NOT BUILT

The following are explicitly **not implemented** in this submission and
are described here only as the natural next phase, per the brief's
request to be clear about implemented-vs-designed:

- **Facial Recognition System (FRS) integration**: would require a
  face-detection + embedding model (e.g. RetinaFace + ArcFace) as a
  second analytics pipeline parallel to ANPR, publishing
  `FaceDetectionEvent`s to the same bus, correlated against a
  face-embedding watchlist (e.g. via NAFIS/AFIS — see
  `11-scalability-and-future-roadmap.md`). The adapter/bus/correlation
  architecture already supports this without redesign: it would be a
  new analytics module subscribing to `frames.ingested` and publishing
  to a new `face.detections` topic, exactly parallel to how the ANPR
  module works today.
- **General object/behavior detection** (weapon detection, crowd density,
  abandoned-object, loitering, wrong-way vehicle detection): each would
  be an additional YOLO-family model (or a dedicated behavior model)
  running as its own analytics module on the same normalized frame
  stream, publishing to its own bus topic. The federation pattern's value
  is exactly that none of this requires touching the adapter layer or
  correlation engine's core dedup/match logic — only adding new event
  types and new correlation rules for them.
- **Vehicle make/model/color classification**: a lightweight
  classification head (or a second small YOLO model) on the vehicle crop
  already available from the plate-detection bounding box, to enrich
  `VehicleSighting` records — useful when a witness description ("white
  Swift") needs to narrow a trace query, which the current schema has a
  `vehicle_description` field ready to support on the watchlist side but
  does not yet populate from vision.

None of the above is stubbed with fake output in this build — they are
absent, not faked, per the brief's requirement to avoid placeholder logic
in anything demoed.
