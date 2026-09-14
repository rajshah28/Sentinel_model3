"""
ANPR pipeline: plate detection (YOLOv8n, fine-tuned for license plates)
+ OCR (EasyOCR) on CPU. Runs on normalized frames coming out of any
vendor adapter -- the pipeline has no knowledge of which vendor
produced the frame, only the common NormalizedFrame schema.

CPU-only environment: frames are downscaled to ~640px width before
detection, and this module is designed to be called on sampled frames
(already sampled upstream by the adapters), not every raw frame.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "yolov8n_plate.pt")

# Populated lazily so importing this module doesn't force a model load
# (e.g. from scripts that only need the schema).
_yolo_model = None
_ocr_reader = None


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO(_MODEL_PATH)
    return _yolo_model


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


@dataclass
class PlateReadResult:
    plate_text: str
    plate_confidence: float
    detection_confidence: float
    vehicle_bbox: Optional[list] = None
    plate_bbox: Optional[list] = None


PLATE_CLEAN_RE = re.compile(r"[^A-Z0-9]")


def clean_plate_text(raw: str) -> str:
    """Uppercase and strip anything that isn't alphanumeric."""
    return PLATE_CLEAN_RE.sub("", raw.upper())


def _downscale(img: np.ndarray, target_width: int = 640) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    if w <= target_width:
        return img, 1.0
    scale = target_width / w
    resized = cv2.resize(img, (target_width, int(h * scale)), interpolation=cv2.INTER_AREA)
    return resized, scale


def detect_and_read_plates(frame_path: str, min_conf: float = 0.25) -> list[PlateReadResult]:
    """
    Run plate detection + OCR on one frame image on disk.
    Returns a list of PlateReadResult, one per detected plate region
    (usually 0 or 1 for these demo clips, but the pipeline supports more).
    """
    img = cv2.imread(frame_path)
    if img is None:
        return []

    small, scale = _downscale(img, 640)
    model = _get_yolo()
    results = model.predict(source=small, verbose=False, conf=min_conf)

    out: list[PlateReadResult] = []
    reader = _get_ocr()

    for r in results:
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            # map back to original resolution
            x1, y1, x2, y2 = [v / scale for v in xyxy]
            x1i, y1i, x2i, y2i = max(0, int(x1)), max(0, int(y1)), min(img.shape[1], int(x2)), min(img.shape[0], int(y2))
            if x2i <= x1i or y2i <= y1i:
                continue

            plate_crop = img[y1i:y2i, x1i:x2i]
            if plate_crop.size == 0:
                continue

            # Upscale small plate crops for better OCR accuracy
            ph, pw = plate_crop.shape[:2]
            if pw < 200:
                factor = 200 / max(pw, 1)
                plate_crop = cv2.resize(plate_crop, (int(pw * factor), int(ph * factor)), interpolation=cv2.INTER_CUBIC)

            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.bilateralFilter(gray, 7, 50, 50)

            ocr_results = reader.readtext(gray)
            if not ocr_results:
                continue

            # Concatenate all detected text fragments (plates sometimes split into 2 OCR boxes)
            texts = sorted(ocr_results, key=lambda t: t[0][0][0])  # left-to-right by bbox x
            raw_text = "".join(t[1] for t in texts)
            ocr_conf = float(np.mean([t[2] for t in texts]))
            plate_text = clean_plate_text(raw_text)

            if len(plate_text) < 3:
                continue

            out.append(PlateReadResult(
                plate_text=plate_text,
                plate_confidence=round(ocr_conf, 3),
                detection_confidence=round(conf, 3),
                vehicle_bbox=None,
                plate_bbox=[x1i, y1i, x2i, y2i],
            ))

    return out
