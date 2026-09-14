# Submission Checklist — Sentinel (Reference Model 3)

Gujarat Police Innovation Hackathon 2026. One place to verify nothing is
missing before submitting. File paths are given so each item can be found
and attached to the submission form immediately.

| # | Required item | Status | File / link | Notes |
|---|---|---|---|---|
| 1 | Solution Presentation (PPT/PDF) | **Done** | `submission/solution_presentation.pptx` | Native PPTX (python-pptx generated, no LibreOffice available in this environment to also export a PDF copy — see "Environment notes" below). 12 slides. Verified via geometric bounds check + text-overflow heuristic (no LibreOffice/PowerPoint available to render a true screenshot — see notes). |
| 2 | Technical Proposal / High-Level Design (HLD) | **Done** | `submission/high_level_design.pdf` | Real PDF (reportlab), 13 pages. Rendered to images and visually inspected page-by-page — one real table-overflow bug and two orphan-page layout issues were found this way and fixed. |
| 3 | Own-feed demo video link | **Pending on you** | — | You're recording this yourself. Add the link here (or directly in the submission form) once ready. |
| 4 | Government-feed demo video + output report link | **Partially done** | Report: `submission/demo4_output_report/` (see below). Video: **pending on you**. | The output report itself is done and packaged. The video is yours to record. |
| 5 | GitHub/GitLab repo link | **Done** | [github.com/rajshah28/Sentinel_model3](https://github.com/rajshah28/Sentinel_model3) | Pushed to `main`. Confirmed public (no sign-in wall) and confirmed the README renders correctly on GitHub's UI, including the embedded architecture diagram image loading — not a broken link. |
| 6 | Hosted platform URL + credentials | **N/A** | — | Not part of this build's scope — the deliverable is the local/Docker-Compose-run system plus documentation, not a persistently hosted instance. Flag me if the submission form requires this and I'll clarify with you how to handle it. |

## Demo 4 output report — file inventory

Three separate real capture runs were made against the live government
sandbox, on different reachability windows (camera availability genuinely
fluctuates run to run — real infrastructure, not simulated). All three
agree on the same honest result. The largest/most recent run is packaged
as the primary submission files.

| File | Contents |
|---|---|
| `submission/demo4_output_report/demo4_raw_detections.csv` | All 45 raw ANPR detections from the primary live-capture run — 18 reachable cameras (up from 7 on the first probe; the sandbox's camera availability changes over time) |
| `submission/demo4_output_report/demo4_plate_format_valid.csv` | The same run, filtered through Indian plate-format validation — 0 rows (headers only), honestly reflecting the real result |
| `submission/demo4_output_report/demo4_output_report.pdf` | The presentable report: states "0 of 45 pass, due to overlay-text false positives — full pipeline verified functional against real infrastructure" directly in the document body |
| `submission/demo4_output_report/demo4_verification_run_*` | An earlier, independent live-capture run (16 detections, 7 reachable cameras) that corroborates the same 0-of-N finding — kept as additional evidence. (A third run, 68 detections from the original 7-camera probe, produced the same result too — see `docs/04-ai-video-analytics.md` for all three.) |

## Architecture diagrams

| File | Use |
|---|---|
| `docs/diagrams/architecture_full.png` (+ `.svg`, `.mmd` source) | Full federation architecture — used in both the HLD and the presentation |
| `docs/diagrams/architecture_overview.png` (+ `.svg`, `.mmd` source) | One-row simplified overview — used on the presentation's title/closing slides and in the README |

## Environment notes (read before assuming something is broken)

- **No LibreOffice/PowerPoint/pandoc/weasyprint/wkhtmltopdf available** in
  this build environment, and no root/sudo to install them. This means:
  - The PPTX could not be rendered to a true screenshot for visual
    verification the way the PDF was. It was instead verified by (a) a
    geometric bounds check confirming every shape sits within the slide
    canvas, and (b) a text-overflow heuristic comparing estimated
    rendered-text height against each textbox's actual height at its
    actual font size — both passed after two real issues found this way
    were fixed (see the PPTX build log in this session). This is real
    verification, but not the same as looking at an actual rendered
    slide — **open it yourself in PowerPoint/Google Slides/LibreOffice
    before presenting**, in case something the heuristic couldn't catch
    slipped through.
  - The HLD PDF, by contrast, **was** rendered to real page images
    (via `pdftoppm`) and visually inspected page-by-page — this caught
    and fixed one genuine table-overflow bug and two orphan-page issues.
    Higher confidence here than on the PPTX.
  - `docker compose up --build` is written correctly against verified
    dependency versions but was never executed end-to-end here (no
    Docker on this machine) — see the README's "Honesty note" under
    "Run it." `run_local.sh` is the path that was actually run,
    repeatedly, all night.

## Credential / git-history check (see conversation for full detail)

- **Confirmed**: the entire git history before this session's work
  consisted of exactly one commit, containing only `.gitignore` — nothing
  else was ever committed, so there is nothing to scrub.
- **Confirmed**: `backend/.env` (holding the real government-sandbox
  email/password) is correctly gitignored and does not appear in
  `git status`, a dry-run `git add -A`, or a direct grep of every file
  that would be staged.
- **Confirmed by direct grep of every staged file** for the literal
  credential string, email, and host: the only match found was the
  sandbox's bare IP address in `README.md`/`docs/`, which you explicitly
  confirmed is fine to keep public (it's useless without the email +
  password, which are correctly excluded).

## To do before you submit

- [x] ~~Confirm the target GitHub repo and push~~ — done:
      [github.com/rajshah28/Sentinel_model3](https://github.com/rajshah28/Sentinel_model3),
      confirmed public with a correctly rendering README.
- [ ] Record the own-feed demo video and government-feed demo video, add
      their links to item 3 and 4 above (and to the submission form).
- [ ] Open `submission/solution_presentation.pptx` yourself in real
      presentation software once, given the rendering-verification gap
      noted above.
- [ ] If the submission form has a "hosted platform URL" field and you do
      want to stand one up, tell me and we'll figure out the fastest real
      option — right now this is marked N/A because it wasn't in scope.
- [ ] Note for future pushes: this machine's git identity (SSH key
      authenticates as GitHub user `rajshah0928`) was added as a
      collaborator on the repo to enable this push. If you want to remove
      that access after the hackathon, do so from
      [repo Settings → Collaborators](https://github.com/rajshah28/Sentinel_model3/settings/access).
