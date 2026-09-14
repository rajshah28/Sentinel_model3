"""
Unit tests for the Indian plate-format filter (Vendor D reporting-layer
only -- see app/adapters/govt_grid_plate_filter.py for why this is
scoped away from the core ANPR pipeline and vendors A/B/C).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters.govt_grid_plate_filter import is_plausible_indian_plate, filter_plausible_plates


def test_valid_indian_plates():
    valid = ["GJ06XY1234", "GJ10AB5566", "MH05S9954", "UP50BY1998", "DL01AB0001"]
    for plate in valid:
        assert is_plausible_indian_plate(plate), f"{plate} should be valid"
    print(f"PASS: {len(valid)} valid Indian plate formats correctly accepted")


def test_overlay_text_false_positives_rejected():
    """The exact real false positives observed against the live sandbox
    (see README.md 'Demo 4' section) must all be rejected."""
    false_positives = [
        "JANPATH", "JANPATK", "JANPATL", "MADHURAM", "VADLAFATAK",
        "VADLAFATAKZ", "13062026", "130620262102", "ONGCOFFICEBS10",
        "4OCUE", "LONEIGE", "UIEIOW", "KOND", "13062026210249",
        "1306202621", "130620262102SAT", "130620262",
    ]
    for plate in false_positives:
        assert not is_plausible_indian_plate(plate), f"{plate} should be rejected"
    print(f"PASS: all {len(false_positives)} real overlay-text false positives correctly rejected")


def test_demo_vendor_plates_correctly_out_of_scope():
    """
    Confirms the filter would (correctly) reject the vendor B/C demo
    plates too -- this is expected and fine, since this filter is never
    applied to vendor A/B/C output. It's tested here only to make the
    scoping decision explicit and verifiable, not because vendor B/C
    detections ever pass through this function in the real pipeline.
    """
    assert not is_plausible_indian_plate("BGY888")  # vendor B demo plate (German-style)
    assert not is_plausible_indian_plate("BRASIL8X337")  # vendor C demo plate (novelty design)
    print("PASS: non-Indian demo plates correctly fail this filter (expected -- never applied to them)")


def test_filter_plausible_plates_on_dicts():
    rows = [
        {"plate_text": "GJ06XY1234", "other": 1},
        {"plate_text": "JANPATH", "other": 2},
        {"plate_text": "MH05S9954", "other": 3},
    ]
    result = filter_plausible_plates(rows)
    assert len(result) == 2
    assert {r["plate_text"] for r in result} == {"GJ06XY1234", "MH05S9954"}
    print("PASS: filter_plausible_plates correctly filters a list of detection dicts")


if __name__ == "__main__":
    test_valid_indian_plates()
    test_overlay_text_false_positives_rejected()
    test_demo_vendor_plates_correctly_out_of_scope()
    test_filter_plausible_plates_on_dicts()
    print("\nAll plate-filter tests passed.")
