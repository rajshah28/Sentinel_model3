# Cost-Benefit Analysis — Statewide Rollout

**This is a hackathon-stage, order-of-magnitude estimate**, built to show
the reasoning shape a real costing exercise would follow — not a
procurement-grade costing. Real figures depend on actual GPU vendor
pricing/discounts at government procurement scale, actual departmental
network conditions, and actual staffing rates, none of which are
knowable from a one-night build. Every number below should be treated as
"the kind of number this would be," not "the number."

## CAPEX (one-time / upfront)

| Item | Basis | Rough estimate |
|---|---|---|
| GPU compute nodes | ~3,400 GPUs (T4/A10-class) at statewide scale (`07-infrastructure-sizing.md`); rough $3,000–6,000/GPU-equivalent node cost inclusive of host server, at government-procurement pricing, not retail | 3,400 × ~$4,500 (mid-estimate) ≈ **$15.3M** | 
| Core cluster infra (Kubernetes control plane, Kafka/event-bus brokers, non-GPU compute nodes for correlation engine + API tier) | Smaller than the GPU line by roughly an order of magnitude — CPU-only nodes, standard cloud/on-prem server pricing | ≈ **$1.5–2.5M** |
| Storage (hot/warm/cold tiers, first-year capacity per `08-network-bandwidth-storage.md`: ~6 TB hot+warm + ~145 TB/year cold) | Object storage hardware/licensing if on-prem, or committed capacity if cloud | ≈ **$0.5–1.5M** first-year build-out (grows yearly on the cold tier) |
| Networking/integration cost per department onboarding (site-to-site VPN or leased line, gateway-side config, adapter development per `03-integration-strategy.md`) | 26 departments, each needing a network link + adapter integration effort; per-department cost varies hugely by department size (a district police unit vs. a citywide Smart City SPV with thousands of cameras), so this is a blended average | ~$50,000–150,000/department × 26 ≈ **$1.3–3.9M** |
| **Rough total CAPEX** | | **≈ $18–23M** (order of magnitude) |

**Sanity check on the dominant line item**: GPU compute is ~65–80% of
CAPEX in this estimate, which is expected — ANPR inference at 80,000
cameras is genuinely GPU-hungry, even with the ~25–50x sampling-rate
saving from the metadata-only, sampled-frame design (`07-infrastructure-sizing.md`).
This is also the line item most sensitive to real procurement pricing
(bulk government GPU deals, cloud reserved-instance pricing, or a hybrid
edge-inference strategy that shifts some load off central GPU pools —
see `11-scalability-and-future-roadmap.md`) and the one most worth
re-deriving carefully before any real budget commitment.

## OPEX (recurring, annual)

| Item | Basis | Rough estimate |
|---|---|---|
| Cloud/hosting (if cloud-hosted GPU/compute rather than owned hardware) | GPU-hours at ~3,400 GPU-equivalent capacity, even assuming significant reserved/committed-use discounting vs. on-demand pricing | If owned hardware (CAPEX above): mainly power/cooling/facilities, roughly 10–15% of GPU CAPEX/year ≈ **$1.5–2.3M/year**. If cloud-rented instead: substantially higher, likely **$8–15M/year** at full statewide GPU utilization — this is the single biggest reason a large state deployment would lean toward owned/colocated GPU infrastructure over pure cloud rental at this scale. |
| Bandwidth (statewide event+crop traffic, `08-network-bandwidth-storage.md`: ~1.6 Gbps sustained peak) | Modest compared to a Model 2 (raw video) design — this is a direct payoff of the metadata-only architecture | ≈ **$0.2–0.5M/year** (leased-line/VPN + egress costs across 26 departments) |
| SOC / monitoring team staffing | A statewide alert/correlation system needs 24/7 human review of watchlist matches and alert triage, not just automated alerting — a reasonable planning figure is a small rotating team (e.g. ~15–25 analysts/operators across shifts) plus a handful of senior engineers/DBAs/ML engineers for platform operations | ≈ **$1.5–3M/year** (blended government + technical staffing rates) |
| Maintenance (model retraining/updates, adapter maintenance as vendor VMS APIs change, standard SRE/on-call) | Ongoing engineering effort — adapters are lightweight per `03-integration-strategy.md`, but 26+ of them still need periodic upkeep as vendor firmware/APIs change | ≈ **$1–2M/year** |
| **Rough total OPEX** | | **≈ $4.2–8M/year** (owned-hardware scenario) or **≈ $11–20M/year** (cloud-rental scenario) |

## Benefit side

### Qualitative

- **Faster stolen-vehicle recovery**: cross-camera ANPR tracing
  (`/api/trace/{plate}`, proven tonight end-to-end — see root `README.md`)
  turns "which of 26 departments might have seen this plate" from a
  manual multi-department phone-and-email process into a single query
  returning a timestamped sighting timeline across every federated
  camera, regardless of which department owns it.
- **Cross-department case correlation**: today, correlating a vehicle or
  suspect sighting across department boundaries requires each department
  to be asked individually, whether informally or via a formal request
  process — a process measured in days. A shared correlation engine
  collapses this to the query latency of a single trace request.
- **Preserves departmental VMS investment**: unlike Model 1 (rip-and-
  replace) or Model 2 (centralize video), no department loses its
  existing, already-paid-for VMS system or has to migrate operational
  video access to a new platform — the cost avoided here is a full
  re-procurement across 26 departments, which is categorically larger
  than this system's CAPEX (see quantitative comparison below).
- **Statewide oversight without statewide video liability**: Home
  Department gets a unified alerting/oversight layer (per
  `10-department-wise-requirements.md`) without the state taking on
  custody of every department's raw video, which limits both the attack
  surface (`05-cybersecurity-architecture.md`) and the legal/privacy
  liability of centralizing sensitive footage.

### Rough quantitative

**Avoided cost of full VMS replacement (Model 1) or centralized video
ingestion (Model 2), vs. this federation approach**:

**Assumption C1**: replacing or re-platforming VMS across 26 departments
at an average of a few thousand cameras each (consistent with the
80,000-camera statewide target) at a rough **$300–600 per camera**
all-in replacement cost (hardware + VMS licensing + installation labor —
a conservative industry planning figure, not a vendor quote) implies:

```
Full VMS replacement cost ≈ 80,000 × $450 (midpoint) ≈ $36M
```

— and that figure only covers hardware/licensing, not the operational
disruption of 26 departments migrating live surveillance systems, which
realistically adds material additional cost and risk not captured in a
per-camera hardware number.

```
This submission's CAPEX estimate  ≈ $18–23M
Avoided Model 1 replacement cost  ≈ $36M+ (hardware/licensing only,
                                     excludes disruption cost)
```

Even at the rough order-of-magnitude level here, federation (Model 3)
CAPEX comes in well under a full-replacement program's hardware/licensing
cost alone, before counting the operational-disruption cost Model 1
would add and the raw-video-centralization bandwidth/storage cost Model 2
would add (`08-network-bandwidth-storage.md`'s ~60x bandwidth-multiplier
finding is the concrete Model 2 comparison point).

**Time-saved value of cross-department trace** (illustrative, not a
formal ROI model): if a manual cross-department vehicle trace today
realistically takes on the order of **1–3 days** of inter-department
coordination for a moderately complex case, and a federated trace query
takes seconds, the operational value is in faster case resolution and
investigator time freed up — genuinely hard to price precisely at
hackathon stage, which is exactly why this section states it
qualitatively first and treats any dollar figure on it as illustrative
only.

## Caveat, stated directly

Every dollar figure in this document is a rough planning-order estimate
built from stated assumptions (GPU count from `07-infrastructure-sizing.md`,
bandwidth from `08-network-bandwidth-storage.md`, and industry-typical
unit costs for VMS hardware/staffing that were not independently sourced
for Gujarat-specific procurement rates). A real costing exercise would
need actual vendor quotes, actual government pay-scale staffing costs,
and a real network-conditions survey across the 26 departments before
any number here should inform an actual budget decision.
