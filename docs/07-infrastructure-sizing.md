# Infrastructure Sizing — Tonight's ~5 Cameras to Statewide 80,000

Rough order-of-magnitude sizing, not a procurement-grade capacity plan.
Every number below is either measured tonight (see `04-ai-video-analytics.md`)
or a stated assumption — assumptions are called out explicitly *before* the
arithmetic that uses them, per the brief's request.

## The core design choice: sampled-frame ANPR, not full real-time video

Tonight's build does not run ANPR on every frame of every camera's video
stream. `app/config.py::VENDOR_SOURCES` samples one frame every **1–2
seconds** per camera (`sample_every_sec: 1.0` or `2.0`), not the native
~25–30 fps of the source footage. This is a deliberate architectural
choice carried into the statewide design, not just a demo shortcut:

- ANPR only needs to catch a vehicle *once* as it passes a camera's field
  of view. A vehicle is typically in frame for several seconds at
  road/junction speeds, so 1 frame/1–2 sec is enough samples to get at
  least one readable plate crop, without processing 25–30x more frames
  than necessary.
- This is the single biggest lever in the entire sizing exercise: it cuts
  required inference throughput by roughly **25–50x** versus naive
  full-frame-rate processing, which is the difference between a sizing
  answer that's plausible for a state government budget and one that
  isn't.

**Assumption A1**: statewide design keeps this same sampling cadence —
1 frame every **1.5 seconds** per camera on average (midpoint of tonight's
1.0–2.0 sec range) — rather than moving to full real-time video analysis.

## Step 1 — total inference load at 80,000 cameras

| Assumption | Value | Basis |
|---|---|---|
| Cameras statewide (target) | 80,000 | Brief's stated roadmap figure |
| Sample interval per camera | 1.5 sec (≈0.67 frames/sec) | A1 above, tonight's actual config values |
| Fraction of cameras active/online at any time | 80% | Realistic allowance for maintenance, offline rural links, planned downtime — not all 80,000 are live simultaneously |

```
Effective active cameras   = 80,000 × 0.80 = 64,000
Total inference throughput = 64,000 cameras × (1 / 1.5 sec) frames/sec/camera
                            = 64,000 × 0.667
                            ≈ 42,700 frames/sec (statewide, sustained)
```

## Step 2 — GPU throughput per accelerator

Tonight's pipeline runs YOLOv8n (plate detection) + EasyOCR (text read) on
CPU at **~0.1–0.2 sec/frame measured** (`04-ai-video-analytics.md`). GPU
inference is materially faster for both stages, but EasyOCR's recognition
step (a CRNN-style sequence model) doesn't accelerate as cleanly as YOLO
detection does, so the estimate below is deliberately conservative rather
than assuming a naive GPU/CPU speedup ratio.

**Assumption A2**: on a mid-tier inference GPU (NVIDIA T4 or A10-class,
the realistic cost/performance tier for a state deployment — not H100-class),
combined detect+OCR pipeline throughput is **~15 frames/sec per GPU**
sustained, once batched across multiple camera streams and accounting for
I/O, decode, and OCR overhead. This assumes:
- Plate detection (YOLOv8n) batched across streams: sub-10ms/frame on a T4.
- OCR remains the bottleneck (~50–60ms/frame equivalent even after GPU
  acceleration and batching), since EasyOCR's recognition head is smaller
  but still sequential per crop.
- Real deployment would validate this with an actual load test before
  committing to a GPU count — treat 15 fps/GPU as a planning assumption,
  not a benchmarked figure.

```
GPUs required = total throughput ÷ throughput per GPU
              = 42,700 frames/sec ÷ 15 frames/sec/GPU
              ≈ 2,850 GPUs
```

Add **20% headroom** for autoscaling burst (peak-hour traffic, festival/
VIP-movement surge deployments, retry/backpressure absorption — the
Kubernetes HPA-on-queue-depth pattern from `06-deployment-architecture.md`):

```
Planning GPU count ≈ 2,850 × 1.2 ≈ 3,400 GPUs statewide
```

| Scale point | Cameras | GPUs (T4/A10-class, planning figure) |
|---|---|---|
| Tonight (demo) | 5 | 0 (CPU-only, sufficient at this scale) |
| Pilot department (e.g. one city traffic police) | ~500–1,000 | 20–40 |
| District rollout (see `11-scalability-and-future-roadmap.md`) | ~10,000 | ~425 |
| Statewide | 80,000 | ~3,400 |

This is an order-of-magnitude planning number, useful for budget
conversations and node-pool provisioning targets — not a number to
commit to a hardware PO without a real load test on production hardware
and real camera footage mix (viewing angle, resolution, and lighting all
materially affect the true fps/GPU figure).

## Step 3 — API / correlation-engine compute sizing

The correlation engine (`app/correlation/engine.py`) does dedup (10-second
window lookup) and a watchlist-table check per detection event — both
cheap, indexed operations, not model inference. Its compute profile is
CPU-bound, I/O-light, and scales with **event rate**, not camera count
directly (since sampling cadence is already fixed per A1).

```
Event rate ≈ total inference throughput (every sampled frame that yields
             a plate read produces one DetectionEvent)
           ≈ 42,700 frames/sec upper bound
           → realistically lower, since only a fraction of sampled frames
             contain a legible plate (tonight's measured detection rate
             ranged 0%–100% across three very different clips — see
             `04-ai-video-analytics.md` — so this is a deliberately
             pessimistic upper bound, not an expected-case number)
```

**Assumption A3**: a single correlation-engine replica (a few CPU cores)
can sustain on the order of **1,000–2,000 dedup+watchlist-check
operations/sec** against an indexed Postgres table (a conservative
estimate for a stateless, mostly-cache-friendly hot path — the watchlist
table is small, tens of thousands of rows at most, so it stays in memory
/ shared buffers easily).

```
Correlation engine replicas ≈ 42,700 ÷ 1,500 ≈ 29, rounded up with
headroom → ~35–40 replicas at full statewide peak load
```

Partitioned by camera/region (as shown in the `06-deployment-architecture.md`
Kubernetes diagram) so no single replica needs global state — each
replica owns dedup/watchlist logic for its assigned camera shard, and the
watchlist table itself (small, read-mostly) can be cached in each
replica's memory or served from a read replica.

The API layer (`APIK` pods) is stateless and scales independently via
standard HPA on request rate / CPU — no special sizing logic beyond
normal web-tier autoscaling, since dashboard/API traffic (human users +
polling clients) is orders of magnitude lower volume than the detection
event stream itself.

## Step 4 — Postgres sizing tier reasoning

**Write load**: dominated by `DetectionRecord` inserts, one per detected
plate read (not one per sampled frame — only frames with a successful
detection produce a row).

**Assumption A4**: statewide, ~10–20% of sampled frames yield a
confident plate detection worth persisting (a blend of tonight's
observed 0%/68%/100% detection rates across very different footage
quality — see `04-ai-video-analytics.md` — weighted toward the lower end
for a realistic mixed statewide camera fleet including low-quality rural
feeds).

```
Detection write rate ≈ 42,700 frames/sec × 0.15 ≈ 6,400 writes/sec (peak)
```

| Postgres tier | When it's sufficient | Why |
|---|---|---|
| Single instance (tonight's build) | Demo / pilot, ≤ ~50–100 cameras | Tonight's actual config: 1 instance, no partitioning, no read replicas. Fine at this scale — write volume is trivial. |
| Vertically scaled single primary + read replicas | Up to a few thousand cameras / low hundreds of writes/sec | Read replicas absorb dashboard/trace query load off the write path; still one logical write target. |
| Time-partitioned tables (e.g. daily/weekly partitions on `detections`) + read replicas | District-scale, thousands of writes/sec | Partition pruning keeps trace/lookup queries fast as the table grows into billions of rows; old partitions can be moved to cheaper storage or dropped per retention policy (`08-network-bandwidth-storage.md`). |
| Sharded by region/department (e.g. Citus, or app-level sharding) | Statewide, ~6,000+ writes/sec sustained | 6,400 writes/sec sustained plus burst is past what a single (even well-tuned) Postgres primary should carry reliably; sharding by department/region aligns naturally with how correlation-engine replicas are already partitioned in Step 3, and with how departments query their own data most of the time. |

**When to shard, concretely**: the trigger isn't a fixed camera count but
sustained write throughput approaching what a single primary's WAL/disk
I/O can absorb with margin — a reasonable rule of thumb is to start
planning the shard/partition migration once sustained writes exceed
roughly **2,000–3,000/sec**, well before hitting the wall, since
re-architecting the data layer under live load is far more expensive than
planning for it at the district-rollout stage (`11-scalability-and-future-roadmap.md`).

## Summary table

| Layer | Tonight | Statewide planning estimate | Confidence |
|---|---|---|---|
| Cameras | 5 | 80,000 | given (brief) |
| Sampled-frame throughput | ~3 frames/sec total | ~42,700 frames/sec (peak, 80% online) | derived from A1 |
| GPUs (T4/A10-class) | 0 (CPU) | ~3,400 with headroom | order-of-magnitude, needs load-test validation |
| Correlation engine replicas | 1 (in-process) | ~35–40, partitioned | order-of-magnitude |
| Postgres | 1 instance | Sharded/partitioned, multiple write nodes | trigger ~2,000–3,000 writes/sec sustained |

All figures above should be re-derived once real statewide camera
resolution/quality mix, actual online-fraction, and a real GPU benchmark
(not tonight's CPU numbers) are available — this is a hackathon-stage
estimate meant to show the sizing *method* is sound, not a number to
budget against directly.
