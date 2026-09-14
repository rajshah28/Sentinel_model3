# Cybersecurity Architecture

Clearly split below: **implemented tonight** vs. **designed for
production** — per the brief's explicit request not to blur the two.

## Implemented tonight

### Authentication & RBAC

- **JWT-based auth** (`backend/app/api/security.py`): bcrypt password
  hashing (`bcrypt` directly — see the passlib incompatibility note
  below), HS256-signed access tokens (`python-jose`), 8-hour expiry.
- **Two roles**: `admin` (statewide access, can run ingestion, sees the
  Watchlist admin page) and `department-user` (scoped to one
  department). Enforced both in the API (`require_admin` dependency;
  every list/query endpoint filters by `user.department` unless
  `role == "admin"`) and in the UI (the Watchlist nav link and admin
  actions are conditionally rendered only for `admin`).
- **Verified**: logging in as `dahod_operator` returns only Dahod City
  Police's one camera from `/api/cameras`, and the Watchlist page/nav
  link is absent — confirmed via a real browser automation pass (see
  root README "How to reproduce the demo").
- A real dependency bug was hit and fixed here: `passlib`'s bcrypt
  backend detection is broken against `bcrypt>=4.1`'s changed version
  API (`AttributeError: module 'bcrypt' has no attribute '__about__'`).
  Rather than pin an old `bcrypt`, the build calls `bcrypt.hashpw`/
  `bcrypt.checkpw` directly — one less unmaintained dependency in the
  chain, and no behavior change for the app.

### Third-party feed credential handling (Vendor D)

The government sandbox grid (Demo 4) authenticates every RTSP/WHEP
connection with credentials embedded in the connection URL
(`rtsp://email:password@host:port/...`), per that grid's own
integration spec. This is exactly the kind of secret a middleware
layer integrating many departments' systems will handle routinely in
production, so it was treated with real production hygiene rather than
demo shortcuts:

- Credentials are read from environment variables
  (`SENTINEL_GOVT_GRID_EMAIL`/`_PASSWORD`), loaded from an operator-
  managed `backend/.env` file that is gitignored and was never typed
  into any AI-assisted tool call during development — the operator
  created and populated that file directly.
- Every code path that might log, return, or otherwise surface a
  constructed RTSP/WHEP URL passes it through a `redact_url()` helper
  (`app/adapters/govt_grid_catalogue.py`) first, which strips the
  embedded `user:password@` down to `***:***@`. This covers: adapter
  connection-attempt logs, catalogue-fetch error messages, and the
  `/api/ingestion/govt-grid/catalogue` API response the dashboard
  renders (confirmed by code review that no other code path touches
  the raw credentialed URL — see grep results during development).
- The one place the *real* URL is used is the single `cv2.VideoCapture`
  connect call itself, which is unavoidable — OpenCV/FFmpeg require the
  credential in the URL for RTSP basic-auth-in-URL schemes like this
  one.
- This is the same pattern that would apply to any department whose
  VMS requires API keys, basic auth, or signed URLs in production (see
  `03-integration-strategy.md`): the adapter owns constructing and using
  the credentialed connection, and nothing downstream of it (bus,
  correlation engine, API, frontend) ever needs or sees the secret.

### Data protection at the application layer

- Passwords are never stored or logged in plaintext.
- The JWT secret is read from `SENTINEL_JWT_SECRET` (environment), not
  hardcoded for deployment (a dev-only literal default exists purely so
  the demo runs without extra setup — flagged directly in the source
  comment).
- API responses are scoped by department at the query level, not
  filtered client-side, so a `department-user` token literally cannot
  retrieve another department's alert/camera/trace data even by calling
  the API directly.

## Designed for production (not implemented tonight)

### TLS in transit

Every network hop in the design terminates or originates TLS:
department → integration layer (mutual TLS recommended, given this
carries law-enforcement-sensitive metadata), integration layer →
dashboard clients (standard TLS via a reverse proxy / API gateway), and
inter-service traffic within the Kubernetes cluster at statewide scale
(service mesh mTLS, e.g. Istio/Linkerd). Tonight's demo runs over plain
HTTP on localhost, appropriate only for a local demo environment.

### Encryption at rest

- PostgreSQL: transparent disk encryption at the volume/filesystem
  level (cloud-managed Postgres offerings provide this natively) plus
  column-level encryption for any field considered especially sensitive
  (e.g. informant-linked watchlist metadata, if added later).
- Evidence frames (cropped detection images): encrypted object storage
  (SSE-S3 or equivalent) with access-logged retrieval, not the local
  plain-disk `data/frames/` used in the demo.

### Audit logging

Every alert acknowledgment, watchlist addition, and cross-department
trace query should be append-only audit-logged with actor identity,
timestamp, and target record — critical for an inter-department law
enforcement system where "who looked up this vehicle and why" is itself
an accountability requirement. Not implemented tonight; the
`AlertRecord.acknowledged` field and the trace endpoint are the natural
audit points to hook this into first.

### API gateway hardening

At statewide scale, the FastAPI backend sits behind an API gateway
providing: rate limiting per department/API-key, request size limits
(relevant given frame uploads), WAF rules against injection, and
centralized JWT validation before traffic reaches application pods —
rather than every backend replica validating tokens independently as
this demo build does inline.

### Secure feed exchange between departments and the integration layer

Production onboarding (see `03-integration-strategy.md`) should require:
site-to-site VPN or a dedicated leased line per department (not public
internet exposure of any camera/VMS endpoint), certificate-based mutual
authentication for each adapter's upstream connection, and network
segmentation so a compromised department's link cannot reach another
department's segment or the core correlation/database layer directly —
only through the bus's normalized event contract.

### Secrets management

Tonight's demo reads secrets from environment variables
(`DATABASE_URL`, `SENTINEL_JWT_SECRET`) — acceptable for a Docker
Compose demo, not for production. Statewide deployment should use a
proper secrets manager (HashiCorp Vault, or the cloud provider's KMS +
secrets service) with rotation, not long-lived environment variables
baked into container specs.
