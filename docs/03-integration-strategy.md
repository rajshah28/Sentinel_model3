# Integration Strategy — Adapter Pattern & Onboarding

## The adapter contract

Every vendor integration implements `app/adapters/base.py::VendorAdapter`:

```python
class VendorAdapter(abc.ABC):
    vendor_name: str
    protocol: str

    def get_camera_info(self) -> CameraInfo: ...
    async def frames(self) -> AsyncIterator[NormalizedFrame]: ...
```

That's the entire surface area. `get_camera_info()` returns a normalized
camera descriptor (ID, department, vendor, protocol, location, status).
`frames()` yields `NormalizedFrame` objects — sampled frames with a saved
image path, camera ID, timestamp, and dimensions — regardless of how the
vendor's system actually delivers video.

Nothing downstream (ANPR pipeline, bus, correlation engine, API) imports
or references a vendor-specific type. This was enforced in the build: the
`NormalizedFrame`/`CameraInfo`/`DetectionEvent` schemas in
`app/models/schema.py` are the only types that cross the adapter boundary.

## The three implemented adapters, and what they each represent

| Adapter | File | Simulates | Native format quirk it hides |
|---|---|---|---|
| `VendorARtspSimAdapter` | `vendor_a_rtsp_sim.py` | A live RTSP/ONVIF stream reader (`cv2.VideoCapture("rtsp://...")` in production; a recorded file standing in for the socket tonight) | Flat, short-key dict response (`{"ok":1,"img":...,"ts_ms":...}`) typical of embedded firmware APIs |
| `VendorBFileBatchAdapter` | `vendor_b_file_batch.py` | A department whose VMS exports batch video files + metadata sidecars rather than exposing any live protocol (common with legacy municipal CCTV) | Nested camelCase JSON-like structure with epoch-seconds timestamps, typical of a VMS export tool |
| `VendorCSnapshotPollAdapter` | `vendor_c_snapshot_poll.py` | An older DVR/NVR exposing a "get current snapshot" HTTP endpoint, polled on an interval (common on low-bandwidth rural deployments) | XML-ish flat attribute response (`DeviceID`, `SnapshotURI`, `Format`) typical of older embedded HTTP camera firmware |

Each adapter's `_vendor_native_*` helper method is where that vendor's
fictional wire format is simulated and then translated — that's the exact
piece of code that would be replaced with a real SDK/HTTP client call
when integrating an actual departmental VMS, without touching anything
else.

## Protocols supported / designed for

**Implemented tonight:**
- RTSP-style continuous stream reads (OpenCV `VideoCapture`)
- Local batch video file ingestion
- Snapshot-poll (single-image HTTP-style) ingestion

**Designed for production onboarding (not built tonight — adapters are
additive, so these are new classes, not architecture changes):**
- **ONVIF Profile S/G** — the industry-standard IP camera discovery and
  streaming protocol; most modern departmental VMS platforms expose it.
  An `OnvifAdapter` would use `python-onvif-zeep` for discovery/PTZ and
  RTSP for the actual stream, feeding the same `frames()` contract.
- **Vendor REST/SDK adapters** — e.g. Hikvision ISAPI, Dahua OpenSDK,
  Milestone XProtect REST API. Each becomes one adapter class that calls
  the vendor SDK and normalizes the response.
- **MQTT/webhook push adapters** — for VMS platforms that push events
  rather than being polled; the adapter would subscribe to the vendor's
  push channel and translate inbound messages into `NormalizedFrame`
  yields, still through the same interface.

## How a new department/vendor onboards (the actual procedure)

1. **Department provides**: camera inventory (ID, location, lat/long),
   the VMS vendor's integration method (RTSP URL pattern, REST API docs,
   or ONVIF endpoint), and network reachability (VPN/leased line to the
   state integration layer — see `05-cybersecurity-architecture.md` for
   the secure-exchange design).
2. **Integration team writes one adapter class** implementing
   `get_camera_info()` and `frames()`, following the existing three as
   templates. Typical effort for a REST/SDK-based vendor: a few hours to
   a day, since only the vendor-specific read logic is new — sampling
   cadence, frame saving, and normalization are already solved.
3. **Register the camera(s)** — call `upsert_camera()` (see
   `app/ingestion/orchestrator.py`) or add to the source configuration
   (`app/config.py::VENDOR_SOURCES` in this demo build; a database-backed
   camera registry in production, see `06-deployment-architecture.md`).
4. **No changes required** to the ANPR pipeline, event bus, correlation
   engine, database schema, or any API endpoint. This was validated
   directly tonight: adding Vendor C after A and B required zero edits to
   any file outside `app/adapters/vendor_c_snapshot_poll.py` and the one
   line registering it in `app/ingestion/adapter_factory.py`.
5. **Department-level RBAC** — create a `department-user` account scoped
   to the new department string; the existing auth/RBAC layer (see
   `05-cybersecurity-architecture.md`) automatically limits that
   department's dashboard view to its own cameras/alerts with no code
   change, since scoping is a query filter on `department`, not a
   per-department code path.
