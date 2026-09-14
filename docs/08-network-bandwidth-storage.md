# Network, Bandwidth & Storage — Why Metadata-Only Federation Changes the Math

## The central design decision: events cross the bus, not video

As established in `01-solution-overview.md` and `02-architecture.md`,
raw video never leaves a department's own VMS/storage. Only three kinds
of payload cross the event bus and reach the shared correlation layer:

1. **Detection events** — plate text, confidence, camera ID, timestamp
   (a few hundred bytes of JSON).
2. **Alert events** — same shape, plus a watchlist match reason.
3. **Evidence crops** — a small cropped/downscaled JPEG of the detected
   plate/vehicle region (not the full frame, and never the full video),
   used tonight for the Live Alert Feed thumbnail and stored under
   `data/frames/`.

This is the entire reason bandwidth planning for Model 3 looks
completely different from what Model 2 (centralized video ingestion)
would require, and it's worth showing the contrast with real numbers
before getting to storage tiers.

## Why this matters: Model 3 vs. Model 2 bandwidth, worked out

**Assumption B1**: a typical department CCTV stream, if centralized as
raw video, runs ~1080p H.264 at a modest bitrate for a fixed security
camera — **~2 Mbps** per stream (conservative; many VMS deployments run
higher for higher frame rates or less aggressive compression).

**Model 2 (centralize raw video)**, at 80,000 cameras, assuming a
realistic **60% concurrently streaming** to the central layer at any
moment (not all cameras push continuously — some are motion-triggered,
some batch-upload):

```
Concurrent streams = 80,000 × 0.60 = 48,000
Bandwidth           = 48,000 × 2 Mbps = 96,000 Mbps ≈ 96 Gbps sustained,
                       statewide, into a central ingestion point
```

That's a sustained ~96 Gbps aggregate inbound pipe (before redundancy)
just for video ingress — before any egress to viewers, before any
replication for durability, and concentrated on whatever data center(s)
host the centralized VMS. This is the bandwidth/single-point-of-failure
concern flagged in `01-solution-overview.md`'s Model comparison table.

**Model 3 (this submission)** — only events + evidence crops cross the
bus:

**Assumption B2**: at the same sampled-frame cadence as tonight
(1 frame/1.5 sec average, from `07-infrastructure-sizing.md` Assumption
A1), and the same ~15% detection-yield assumption (A4), each department's
adapter emits a payload of roughly:
- Detection event JSON: ~0.5 KB
- Evidence crop JPEG (downscaled plate/vehicle crop, not full frame):
  **~30 KB** (a few hundred pixels wide, JPEG-compressed — tonight's
  actual saved crops are in this range)

```
Peak statewide event+crop rate ≈ 42,700 frames/sec sampled
                                  × 15% detection yield
                                ≈ 6,400 detections/sec (from
                                  07-infrastructure-sizing.md Step 4)

Bandwidth = 6,400/sec × (0.5 KB event + 30 KB crop)
          = 6,400 × 30.5 KB/sec
          ≈ 195,200 KB/sec
          ≈ 1,560 Mbps ≈ 1.6 Gbps sustained, statewide
```

| | Model 2 (centralize raw video) | Model 3 (this submission — metadata/events only) |
|---|---|---|
| Sustained statewide bandwidth (peak) | ~96 Gbps | ~1.6 Gbps |
| Ratio | 1x | **~60x less** |
| What crosses the bus | Full video streams | Detection/alert JSON + small evidence crops |
| Where raw video lives | Centralized (new storage/liability surface) | Stays at the department's existing VMS, under its existing retention policy |

The ~60x reduction is the direct, quantified payoff of the "metadata-only
federation" design principle stated in `01-solution-overview.md` — this
is what makes statewide integration a realistic network/bandwidth ask
rather than a multi-hundred-Gbps backbone procurement project.

**What still needs department-to-integration-layer bandwidth**: each
department's own adapter still needs to *read* its local video to run
ANPR (or, in the future architecture, send frames to a regional GPU
pool — see `11-scalability-and-future-roadmap.md`'s note on edge vs.
regional inference). That read happens over the department's own
internal network, not the statewide bus, so it does not add to the
cross-department bandwidth figure above; it only appears if ANPR
inference itself is centralized rather than run at/near the edge, which
is a deployment-topology choice made per district, not a hard
architectural requirement of Model 3.

## Storage tiers vs. retention windows

The problem statement calls out both a **short (7-day)** and a
**longer (15+ day)** retention expectation. These map to different
storage tiers with different cost/access-latency tradeoffs — a single
flat retention policy would either be too expensive (everything hot) or
too slow to retrieve from for active investigations (everything cold).

| Tier | What's stored | Retention window | Storage class | Why |
|---|---|---|---|---|
| **Hot / local** | Full-resolution evidence crops + all detection/alert records for recent activity | 0–7 days | Fast SSD-backed storage, close to the correlation engine (or department-local, per department's existing retention policy for raw video itself) | Matches the brief's 7-day window; this is the "active investigation" tier — an officer following up on a same-week incident needs low-latency retrieval, not a cold-storage restore request. |
| **Warm** | Evidence crops + detection records, downsampled/compacted where practical | 7–15+ days (through the brief's second retention marker) | Standard object storage (S3-compatible), still online but not the fastest/most expensive tier | Bridges the gap between "actively worked case" and "closed unless reopened" — still retrievable within seconds/minutes, at meaningfully lower cost than the hot tier. |
| **Cold / archival** | Evidence crops + detection/alert metadata only (no raw video, which was never centralized in the first place) | Beyond 15 days, out to whatever evidentiary/legal retention period applies (often much longer for law-enforcement records — a legal/records-policy decision, not a technical one) | Cold object storage / archival tier (e.g. Glacier-class), lifecycle-policy-managed | Chain-of-custody and evidentiary needs can outlive the "operationally useful" window by months or years; cold tier keeps this affordable at 80,000-camera scale, since it's low-frequency-access by construction. |

Note the asymmetry versus Model 2: because raw video was never
centralized, there's no statewide raw-video storage bill at any tier —
each department keeps managing its own video retention exactly as it
does today (`01-solution-overview.md`). The storage math below is for
the metadata/evidence-crop layer only, which is what this system
actually needs to plan capacity for.

## Storage math: evidence crops + detection records at 80,000 cameras

**Assumptions** (stated explicitly, order-of-magnitude):

| Assumption | Value | Basis |
|---|---|---|
| B3 — detections/alerts worth keeping an evidence crop for, per camera per day | 200 | A camera sampling ~0.67 fps (A1) over a 16-hour active daylight-weighted window with ~15% detection yield (A4) yields on the order of a few hundred plate reads/day per active camera; 200/day is a round mid-estimate, not every sampled frame with a detection needs a *retained* crop if deduped sightings of the same vehicle within a short window collapse to one record (per the 10-second dedup window in `02-architecture.md`) |
| B4 — evidence crop size | 30 KB | Same as B2 above (small JPEG crop, not full frame) |
| B5 — detection record size in Postgres/warm store | ~1 KB (plate text, confidence, camera ID, timestamp, foreign keys, indexes) | Typical relational row + index overhead |
| B6 — fraction of cameras actively producing data on a given day | 80% | Same as `07-infrastructure-sizing.md` Assumption A1 online-fraction |

```
Active cameras/day        = 80,000 × 0.80 = 64,000
Evidence crops/day         = 64,000 × 200 = 12,800,000 crops/day
Crop storage/day           = 12,800,000 × 30 KB ≈ 384,000,000 KB
                            ≈ 384 GB/day (evidence crops only)
Detection-record storage/day = 12,800,000 × 1 KB ≈ 12,800,000 KB ≈ 12.8 GB/day
Total new data/day         ≈ 384 GB + 12.8 GB ≈ ~397 GB/day, statewide
```

Rolling this into the tiered retention windows:

```
Hot tier   (7 days):   397 GB/day × 7   ≈ 2.8 TB   (fast storage)
Warm tier  (8–15 days, ~8 more days):
                        397 GB/day × 8   ≈ 3.2 TB   (standard object storage)
Cold tier  (beyond 15 days, accumulating):
                        397 GB/day × 365 ≈ ~145 TB/year (archival storage,
                        metadata + crops only — cheap per-GB tier)
```

| Tier | Rolling size | Storage class cost profile |
|---|---|---|
| Hot (7-day rolling window) | ~2.8 TB | Highest $/GB, lowest latency |
| Warm (next ~8-day window) | ~3.2 TB | Mid $/GB |
| Cold (annual accumulation) | ~145 TB/year | Lowest $/GB, lifecycle-policy managed, multi-year accumulation for legal retention |

Even the annual cold-tier accumulation (~145 TB/year) is a modest,
budgetable object-storage footprint for a state government — nowhere
near the ~96 Gbps / petabyte-scale-per-week figure Model 2's raw video
centralization would imply at the same camera count. That gap is the
concrete payoff of the metadata-only federation design.

## Tonight's actual implementation vs. this design

| | Implemented tonight | Designed for scale |
|---|---|---|
| Evidence crop storage | Local disk, `data/frames/`, no lifecycle policy, no tiering | Hot/warm/cold object storage tiers as above, with automated lifecycle policies |
| Retention enforcement | None — demo data persists indefinitely on local disk | Automated tier transitions + deletion/archival per the 7-day / 15-day / legal-retention windows |
| Bandwidth | Single host, no network hop between components | mTLS department-to-gateway links sized per department's detection volume (see `05-cybersecurity-architecture.md`) |
