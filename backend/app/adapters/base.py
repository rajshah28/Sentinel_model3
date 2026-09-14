"""
The adapter interface: the single contract every vendor integration must
implement. Adding a new department/vendor means writing one class here
that implements VendorAdapter — nothing in the bus, correlation engine,
ANPR pipeline, or API changes.
"""
from __future__ import annotations

import abc
from typing import AsyncIterator

from app.models.schema import CameraInfo, NormalizedFrame


class VendorAdapter(abc.ABC):
    """
    Base class for all vendor feed adapters.

    Each concrete adapter owns exactly one vendor-specific ingestion path
    (RTSP-style stream, batch video file, snapshot polling API, ...) and is
    responsible for translating that vendor's native format into the
    common NormalizedFrame schema. Nothing about a vendor's SDK, file
    layout, or metadata format leaks past this boundary.
    """

    vendor_name: str
    protocol: str

    @abc.abstractmethod
    def get_camera_info(self) -> CameraInfo:
        """Return the normalized camera descriptor for this feed."""
        raise NotImplementedError

    @abc.abstractmethod
    async def frames(self) -> AsyncIterator[NormalizedFrame]:
        """
        Yield normalized frames one at a time. Implementations sample
        frames at whatever cadence suits their source (e.g. every N
        seconds of footage for a recorded-video demo) rather than
        every raw frame, and save each sampled frame to disk, returning
        its path in the NormalizedFrame.
        """
        raise NotImplementedError
        yield  # pragma: no cover - makes this an async generator for type checkers
