"""
Indian vehicle plate format validation, applied ONLY to Vendor D
(government sandbox grid) output -- a post-filter between raw ANPR
detections and anything that reports on them (the Demo 4 report
generator, the Govt Grid dashboard view).

Why scoped to Vendor D only: vendors A/B/C use demo footage with
non-Indian plates (a German plate "B GY 888" / cleaned "BGY888", and a
Japan/Brasil novelty plate) specifically because that's the real,
available public-domain sample footage -- applying an Indian-format
filter there would break the already-verified BGY888 watchlist-match
demo for no benefit. This module is therefore never imported by
app/anpr/pipeline.py, app/correlation/engine.py, or any vendor A/B/C
adapter -- only by the Vendor D reporting path.

Format (standard Indian registration plate, per RTO convention):
  <2 letters state code><2 digits district code><1-2 letters series><1-4 digits number>
  e.g. GJ06XY1234, MH05S9954, UP50BY1998

This intentionally does NOT catch every real-world edge case (BH-series
plates, older single-letter-series plates before RTO series expansion,
EV green plates, diplomatic plates) -- it is a pragmatic filter for
distinguishing "this looks like a real plate" from "this is clearly
overlay text" (e.g. "JANPATH", "MADHURAM", a burned-in date stamp),
which is the actual problem it was built to solve. See
docs/04-ai-video-analytics.md for the false-positive finding this
addresses.
"""
from __future__ import annotations

import re

# 2 letters (state) + 2 digits (district) + 1-2 letters (series) + 1-4 digits (number)
INDIAN_PLATE_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{1,4}$")


def is_plausible_indian_plate(plate_text: str) -> bool:
    """
    True if plate_text matches the standard Indian registration plate
    format. plate_text is expected already-cleaned (uppercase,
    alphanumeric only) as produced by app.anpr.pipeline.clean_plate_text
    -- this function does not itself strip/normalize anything, so a
    caller passing raw OCR output with spaces/punctuation will (correctly)
    fail validation.
    """
    return bool(INDIAN_PLATE_RE.match(plate_text))


def filter_plausible_plates(rows: list[dict], plate_field: str = "plate_text") -> list[dict]:
    """
    Given a list of detection-shaped dicts (as built by
    scripts/generate_govt_feed_report.py::build_report), returns only
    the entries whose plate text matches the Indian plate format.
    """
    return [r for r in rows if is_plausible_indian_plate(r[plate_field])]
