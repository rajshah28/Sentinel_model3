"""
Catalogue client for the government sandbox camera grid (Vendor D).

Per the integration reference: "Always start from the catalogue rather
than hard-coding endpoints... the camera set can change." This module
is the single place that fetches the camera catalogue and builds
per-camera stream URLs -- nothing else in the Vendor D adapter
hardcodes a camera id or URL pattern.

Supports two catalogue shapes, since the reference doc changed between
drafts during this integration:
  1. GET http://<host>/api/ingest  -> {"cameras": [{id, location, codec,
     live, urls: {rtsp, whep, hls}}, ...]}
  2. GET https://<host>/cameras.json -> a list or {"cameras": [...]}
     of camera ids/metadata, with RTSP/WHEP URLs built from a fixed
     pattern (rtsp://<host>:8554/stream/<id>) rather than being present
     in the response -- this is the shape actually confirmed live.

Credentials (email + password) are supplied via SENTINEL_GOVT_GRID_EMAIL
/ SENTINEL_GOVT_GRID_PASSWORD (see app/config.py) and are embedded in
constructed RTSP/WHEP URLs exactly as the reference doc specifies
(percent-encoded email, rtsp://email:password@host:port/...). Every log
line involving a URL goes through redact_url() first -- the password
must never appear in a log file, exception message, or database row.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

from app.config import (
    GOVT_GRID_CATALOGUE_URL,
    GOVT_GRID_EMAIL,
    GOVT_GRID_FALLBACK_CAMERA_IDS,
    GOVT_GRID_PASSWORD,
)

logger = logging.getLogger("sentinel.govt_grid.catalogue")

_REDACT_RE = re.compile(r"(://)[^/@]+:[^/@]+(@)")


def redact_url(url: str) -> str:
    """Replaces any embedded user:password@ with user:***@ for safe logging."""
    return _REDACT_RE.sub(r"\1***:***\2", url)


@dataclass
class CatalogueCamera:
    camera_id: str
    location: str
    codec: str
    live: bool
    rtsp_url: str
    whep_url: Optional[str]
    hls_url: Optional[str]
    raw: dict


class CatalogueError(RuntimeError):
    pass


def _build_credentialed_url(scheme: str, host: str, port: int, path: str) -> str:
    if not GOVT_GRID_EMAIL or not GOVT_GRID_PASSWORD:
        raise CatalogueError(
            "SENTINEL_GOVT_GRID_EMAIL / SENTINEL_GOVT_GRID_PASSWORD are not both set. "
            "RTSP/WHEP on this grid require per-connection credentials embedded in the URL."
        )
    encoded_email = quote(GOVT_GRID_EMAIL, safe="")
    encoded_password = quote(GOVT_GRID_PASSWORD, safe="")
    return f"{scheme}://{encoded_email}:{encoded_password}@{host}:{port}{path}"


def _build_fallback_cameras(host: str) -> list[CatalogueCamera]:
    """
    Builds CatalogueCamera entries directly from the documented
    cam01..cam30 id range and the fixed RTSP/WHEP URL pattern, without
    ever having fetched a real catalogue response. Used only when
    SENTINEL_GOVT_GRID_USE_FALLBACK_IDS is explicitly set AND the real
    catalogue endpoint could not be reached/authenticated. `live` is
    left True (unverified) since there is no catalogue response to read
    a real status from -- callers relying on this path should expect
    some entries to fail to connect and treat that as normal, not a bug.
    """
    cameras = []
    for cam_id in GOVT_GRID_FALLBACK_CAMERA_IDS:
        cameras.append(CatalogueCamera(
            camera_id=cam_id,
            location=f"{cam_id} (fallback id range, no catalogue metadata available)",
            codec="unknown",
            live=True,
            rtsp_url=_build_credentialed_url("rtsp", host, 8554, f"/stream/{cam_id}"),
            whep_url=_build_credentialed_url("http", host, 8889, f"/stream/{cam_id}/whep"),
            hls_url=None,
            raw={},
        ))
    logger.info("Built %d fallback camera entries from documented id range", len(cameras))
    return cameras


def fetch_catalogue(host: str, timeout: float = 10.0) -> list[CatalogueCamera]:
    """
    Fetches the camera catalogue and returns normalized CatalogueCamera
    entries. Raises CatalogueError on any failure (unreachable host,
    non-200, unexpected shape, missing credentials) rather than silently
    returning an empty list.
    """
    if not host:
        raise CatalogueError(
            "No government grid host configured (SENTINEL_GOVT_GRID_HOST is empty). "
            "This must be supplied explicitly -- never inferred or hardcoded."
        )

    catalogue_url = GOVT_GRID_CATALOGUE_URL or f"http://{host}/api/ingest"
    logger.info("Fetching catalogue from %s", redact_url(catalogue_url))

    session = requests.Session()
    if GOVT_GRID_EMAIL and GOVT_GRID_PASSWORD:
        session.auth = (GOVT_GRID_EMAIL, GOVT_GRID_PASSWORD)

    try:
        resp = session.get(catalogue_url, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            if GOVT_GRID_FALLBACK_CAMERA_IDS:
                logger.warning(
                    "Catalogue at %s redirected to %s (needs a browser/cookie "
                    "session, not basic auth) -- using the documented fallback "
                    "camera-id range (SENTINEL_GOVT_GRID_USE_FALLBACK_IDS is set) "
                    "instead of a real catalogue fetch.",
                    redact_url(catalogue_url), resp.headers.get("location", "?"),
                )
                return _build_fallback_cameras(host)
            raise CatalogueError(
                f"Catalogue at {redact_url(catalogue_url)} redirected to "
                f"{resp.headers.get('location', '?')} -- this endpoint needs a "
                f"browser/cookie session rather than basic auth (confirmed: basic "
                f"auth and common header/query-param auth all still redirect to "
                f"{resp.headers.get('location', '?')}). Set "
                f"SENTINEL_GOVT_GRID_USE_FALLBACK_IDS=1 to use the documented "
                f"cam01..cam30 id range directly instead, or set "
                f"SENTINEL_GOVT_GRID_CATALOGUE_URL to a real, non-redirecting "
                f"catalogue endpoint if one exists."
            )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        if GOVT_GRID_FALLBACK_CAMERA_IDS:
            logger.warning("Could not reach catalogue at %s (%s) -- using fallback camera-id range.",
                            redact_url(catalogue_url), e)
            return _build_fallback_cameras(host)
        raise CatalogueError(f"Could not reach catalogue at {redact_url(catalogue_url)}: {e}") from e
    except ValueError as e:
        raise CatalogueError(f"Catalogue at {redact_url(catalogue_url)} did not return valid JSON: {e}") from e

    if isinstance(data, dict):
        entries = data.get("cameras") or data.get("streams") or data.get("items")
        if entries is None:
            raise CatalogueError(f"Unexpected catalogue response shape: keys={list(data.keys())}")
    elif isinstance(data, list):
        entries = data
    else:
        raise CatalogueError(f"Unexpected catalogue response type: {type(data)}")

    cameras: list[CatalogueCamera] = []
    for entry in entries:
        try:
            # Entries may be bare id strings ("cam01") or objects.
            if isinstance(entry, str):
                entry = {"id": entry}

            cam_id = str(entry.get("id") or entry.get("camera_id") or entry.get("stream_id"))
            urls = entry.get("urls") or {}

            explicit_rtsp = urls.get("rtsp") or entry.get("rtsp_url") or entry.get("rtsp")
            if explicit_rtsp:
                rtsp_url = explicit_rtsp
            else:
                rtsp_url = _build_credentialed_url("rtsp", host, 8554, f"/stream/{cam_id}")

            explicit_whep = urls.get("whep") or entry.get("whep_url") or entry.get("whep")
            if explicit_whep:
                whep_url = explicit_whep
            elif GOVT_GRID_EMAIL and GOVT_GRID_PASSWORD:
                whep_url = _build_credentialed_url("http", host, 8889, f"/stream/{cam_id}/whep")
            else:
                # WHEP is optional (browser preview only, not used by the ANPR
                # pipeline) -- leave it unset rather than failing the whole
                # catalogue fetch over a missing credential that only the
                # RTSP path (mandatory, used below) actually requires.
                whep_url = None

            hls_url = urls.get("hls") or entry.get("hls_url") or entry.get("hls")

            cameras.append(CatalogueCamera(
                camera_id=cam_id,
                location=str(entry.get("location") or entry.get("name") or cam_id),
                codec=str(entry.get("codec") or "unknown"),
                live=bool(entry.get("live", entry.get("status") == "live" or entry.get("live_status", True))),
                rtsp_url=rtsp_url,
                whep_url=whep_url,
                hls_url=hls_url,
                raw=entry,
            ))
        except CatalogueError:
            raise
        except Exception as e:  # noqa: BLE001 - one malformed entry shouldn't kill the whole catalogue
            logger.warning("Skipping malformed catalogue entry %r: %s", entry, e)

    logger.info("Catalogue returned %d camera(s): %s", len(cameras), [c.camera_id for c in cameras])
    return cameras
