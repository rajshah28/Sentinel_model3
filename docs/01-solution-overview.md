# Solution Overview — Reference Model 3: VMS Federation & Middleware

## The problem

Gujarat's CCTV estate spans 26 departments on heterogeneous vendor VMS
platforms, with a roadmap to ~80,000 cameras statewide. Any statewide
capability — ANPR-based vehicle tracing, cross-department alerting, a
unified command dashboard — has to work *across* that heterogeneity
without waiting for 26 departments to standardize on one vendor first.

## Why Model 3 (Federation & Middleware) over the alternatives

| Model | Approach | Why not chosen here |
|---|---|---|
| Model 1 | Full VMS replacement (rip-and-replace) | Not viable at this scale/timeline: 26 departments, sunk procurement costs, operational disruption during replacement, and no guarantee every department can migrate on the same schedule. |
| Model 2 | Centralized video ingestion & storage | Statewide raw video centralization at 80,000 cameras is a massive bandwidth and storage commitment (see `08-network-bandwidth-storage.md`), and creates a single point of failure and a single very large attack surface for sensitive footage. |
| **Model 3 (this submission)** | **Federation & middleware layer**: adapters normalize each department's existing feed/metadata; only *metadata and events* flow through a shared bus; raw video stays where it already lives | Departments keep their existing VMS investment and operational control; the state gets a unified analytics/alerting layer without a video-centralization project. Fastest realistic path from "26 disconnected systems" to "one correlated view," and the only model where onboarding a new department is additive (one new adapter) rather than a re-platforming project. |
| Model 4 | Edge-AI-only, no central correlation | Can't do cross-camera/cross-department vehicle tracing — the hackathon's stated technical evaluation focus — if detections never leave the edge device. |
| Model 5 | Hybrid cloud-native SaaS platform | Reasonable long-term target, but implies a procurement/vendor relationship and multi-tenant cloud commitment that's a program decision, not something a hackathon prototype should presuppose. Model 3's bus/adapter pattern is actually a clean on-ramp to Model 5 later (see `11-scalability-and-future-roadmap.md`), not a competing path. |

## What this submission actually is

A working middleware layer with four load-bearing parts, each proven to
run (not just diagrammed — see the root `README.md` "Demo credentials"
and "How to reproduce" sections for live verification steps):

1. **Adapter layer** — one common interface (`VendorAdapter`), three
   concrete implementations with genuinely different ingestion
   mechanics and native metadata shapes, normalizing into one schema.
2. **Event bus** — every detection, alert, and status update flows
   through publish/subscribe topics, not direct function calls between
   modules. This is what makes the "federation" real in the code, not
   just the architecture diagram.
3. **Correlation engine** — the single place that decides "this is a
   vehicle sighting" and "this is a watchlist match," subscribing to
   the bus and never touching a vendor's native format directly.
4. **ANPR analytics** — real YOLOv8n + EasyOCR plate reading running on
   actual sampled video frames, feeding the bus.

## Key innovations in this submission

- **Vendor-agnostic by construction, not by convention.** Adding a 4th
  department means writing one adapter class implementing `frames()`
  and `get_camera_info()` — nothing in the bus, correlation engine, ANPR
  pipeline, or API changes. See `03-integration-strategy.md`.
- **Metadata-only federation.** Raw video never leaves its source system's
  storage; only detection events, timestamps, camera IDs, and cropped
  evidence frames cross the bus. This keeps each department's video
  retention/ownership policy intact while still enabling statewide
  correlation — directly addressing the brief's requirement to integrate
  *without* centralizing raw video storage.
- **One correlation engine, many feeds.** Cross-camera vehicle tracing
  (`/api/trace/{plate}`) works identically whether the two sightings came
  from an RTSP-style feed in Valsad or a snapshot-poll DVR in Somnath,
  because both were normalized to the same schema before correlation ever
  sees them.

## Objectives

1. Prove the federation pattern end-to-end on real (not mocked) video,
   real ANPR, and a real watchlist match with a live alert.
2. Make vehicle cross-camera tracing — the hackathon's stated evaluation
   focus — a first-class, fast API, not an afterthought query.
3. Keep the architecture honestly incremental: every "at statewide scale
   this becomes X" claim in the docs points at a specific component
   already built tonight that would be swapped or scaled, not a
   hand-wave (see `02-architecture.md` and `07-infrastructure-sizing.md`).
