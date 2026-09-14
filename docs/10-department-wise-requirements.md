# Department-Wise Onboarding Requirements

This document applies the onboarding procedure already defined in
`03-integration-strategy.md` ("How a new department/vendor onboards")
to specific departments relevant to Gujarat Police's 26-department CCTV
integration mandate. It does not re-derive the onboarding mechanics —
every department below onboards via the same four-step procedure
(camera inventory + integration method + network reachability → one
adapter class → camera registration → department-scoped RBAC account).
What differs per department is *what they provide* and *what they
consume back*.

Tonight's build demonstrates this pattern concretely with three
departments already onboarded as distinct adapters — Valsad Traffic
Police (RTSP-style), Dahod City Police (file batch), Somnath Traffic
Police (snapshot-poll) — plus Jamnagar City Police and Dwarka Traffic
Police as status-only camera entries (`backend/app/config.py`). The
table below extends that same pattern to the department types named in
the brief and other departments realistic for Gujarat's 26-department
scope.

## What every department provides (common to all, per `03-integration-strategy.md`)

1. Camera inventory: camera ID, location name, lat/long.
2. VMS vendor's integration method: RTSP URL pattern, REST/SDK API docs,
   or ONVIF endpoint (see `03-integration-strategy.md`'s "Protocols
   supported / designed for" section for the concrete protocol options).
3. Network reachability: VPN or leased line to the integration layer,
   secured per `05-cybersecurity-architecture.md`'s "Secure feed exchange"
   design.
4. A designated department point of contact for the department-scoped
   RBAC account (`department-user` role, per `05-cybersecurity-architecture.md`).

## Department-by-department

| Department | Camera inventory characteristics | Likely VMS vendor / integration method | Network connectivity | What they consume back |
|---|---|---|---|---|
| **Home Department** | No cameras of its own — the statewide oversight body | N/A (consumes, does not feed) | Access to the integration layer's admin/dashboard tier, not a device-level feed link | Statewide alert oversight, cross-department trace queries, aggregate camera-health/status view across all 26 departments — the `admin` role demonstrated tonight (sees all departments, Watchlist admin) is exactly this access pattern |
| **Traffic Police (district-level, e.g. Valsad, Somnath, Dwarka)** | Junction/highway cameras, often existing ANPR-adjacent deployments already | Mix of RTSP-capable IP cameras (`OnvifAdapter`-style, `03-integration-strategy.md`) and older snapshot-poll DVRs on rural highway stretches (`VendorCSnapshotPollAdapter`-style) | District-level VPN link; highway/rural sites may have lower-bandwidth links, favoring snapshot-poll over continuous streaming | Direct camera-level alerts (watchlist match at their own junction), vehicle trace queries scoped to their own + adjoining districts for pursuit/investigation support |
| **District Police (e.g. Dahod City Police)** | Urban static cameras — parking areas, bus stands, market junctions | Often legacy municipal VMS exporting batch video + metadata sidecars rather than a live protocol (`VendorBFileBatchAdapter`-style — tonight's Dahod integration is exactly this case) | Standard department network link; batch-export model tolerates intermittent connectivity better than live streaming | Department-scoped dashboard (own cameras/alerts only, enforced by the `department-user` RBAC scope verified tonight), local watchlist alerts, ability to raise a case-linked trace query |
| **Municipal Corporations / Smart City SPVs** | Largest camera counts per department — city-wide surveillance networks (traffic, public safety, civic infrastructure) already built under Smart City programs | Typically a modern commercial VMS with a REST/SDK API (e.g. Hikvision ISAPI, Milestone XProtect — both named as designed-for adapters in `03-integration-strategy.md`) | Often already has metro-area fiber/network backbone; integration is more likely bandwidth-capable for continuous RTSP than rural departments | Cross-department correlation for city-boundary-crossing vehicle traces (a vehicle often transits multiple jurisdictions within a city+district), Traffic Police visibility into civic camera feeds without owning them |
| **RTO (Regional Transport Office)** | Few or no CCTV cameras of its own; primarily a *data consumer* of the correlation engine's output, not a camera-feed provider | N/A on the feed side; on the consumption side, this is the most natural future integration point for **VAHAN** registration lookups (see `11-scalability-and-future-roadmap.md`) | API-level access to the trace/alert endpoints, not a device feed link | Vehicle trace results enriched with registration-linked plate context — an RTO officer's core interest is "who owns this plate and is the vehicle's registration/fitness/tax status valid," which is exactly the VAHAN-enrichment roadmap item in `11-scalability-and-future-roadmap.md`, not raw camera footage |
| **Food & Civil Supplies (PDS)** | Few or no dedicated CCTV; interested in specific vehicle movement, not general surveillance | N/A on the feed side (may optionally contribute cameras at ration-distribution depots/warehouses if any exist) | API-level access to trace queries filtered/tagged for PDS-relevant vehicle categories | PDS vehicle movement tracking — e.g. tracing a specific registered ration-truck plate across the camera network to confirm route adherence/diversion, directly matching the brief's example use case for this department |
| **GSRTC / Transport Department** | Bus depot and terminal cameras, where present | Mix of legacy DVR (snapshot-poll) at older depots and modern IP camera systems at newer terminals | Depot-level network links, often lower bandwidth in rural depots | Fleet vehicle tracing (stolen/misused GSRTC vehicles), depot-area alert feed |
| **Forensic Science Laboratory (FSL)** | No cameras of its own; a specialized downstream consumer | N/A on the feed side | API-level access, likely to evidence-crop retrieval specifically (not live dashboard use) | Evidence frame retrieval for a specific alert/case (the cropped detection images described in `08-network-bandwidth-storage.md`), with the audit-logged access pattern designed in `05-cybersecurity-architecture.md` — chain-of-custody matters here more than for any other consumer |
| **Excise Department** | Few dedicated cameras; check-post cameras where they exist | Snapshot-poll or batch-export style at check-posts, similar profile to rural Traffic Police sites | Check-post network links, often the lowest-bandwidth sites in the whole estate | Watchlist alerts scoped to excise-relevant vehicle categories (e.g. suspected illicit-transport vehicles), trace queries across check-post camera chains |

## Reading this table against the adapter pattern

The variation across departments above is entirely in **column
2–3** (what kind of camera estate and network link they have) — the
integration mechanics in column 4 onward are uniform, because every
department, regardless of type, ends up behind the same
`VendorAdapter` interface and the same department-scoped RBAC query
filter (`03-integration-strategy.md`, `05-cybersecurity-architecture.md`).
A department with zero cameras of its own (Home Department, RTO, Food &
Civil Supplies, FSL) still onboards — just as a pure *consumer* of the
API/dashboard layer rather than a *feed provider*, which the existing
`admin` vs. `department-user` role split already supports without any
new role type being required.

This is the concrete demonstration of the claim in
`01-solution-overview.md`: "adding a 4th department means writing one
adapter class... nothing in the bus, correlation engine, ANPR pipeline,
or API changes" — extended here to show it holds even for departments
whose relationship to the system is consumption rather than ingestion.
