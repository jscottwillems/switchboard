# Switchboard status

Shared status log. When CLERK started, `ARCHITECTURE.md`, `DATA_MODEL.md`, `SECURITY.md`, and `DECISIONS.md` were not in the repository. Those documents are not created here. `API_CONTRACTS.md` and `EVENTS.md` contain the CLERK handoff this assignment required. Blockers are listed below.

## HANDOFF — CLERK — 2026-09-25T20:45:58Z

### Completed

- Canonical `EvidencePackage` and related report types (`ReportDocument`, `CampaignSummary`, `MachineReadableExport`, `PdfReadyDocument`) with fixed fact-class / epistemic-layer pairs.
- Provisional mocks for the missing CallSession, SHERLOCK observation, and WATSON campaign inputs (`clerk.provisional_upstream.v0`). Packaging copies those inputs and does not promote raw observations or invent campaign links.
- Synthetic fixtures labeled `synthetic: true`, producing a single-call report, a multi-call campaign report, a technical incident report, and a machine-readable JSON export.
- Renderers for JSON, structured Markdown, A4 PDF-ready HTML, CSV tables, and campaign summaries.
- RADAR open-report adapter (`RadarReportCatalog`) plus JSON Schemas. No RADAR UI and no HTTP server.
- ADR 0001 for provenance and the handoff.

### Files changed

- `pyproject.toml`, `.gitignore`
- `src/switchboard/clerk/` — schemas, packaging, provisional adapters, fixtures, renderers, pipeline, RADAR catalog
- `tests/test_schema.py`, `tests/test_reports.py`, `tests/test_radar.py`
- `examples/synthetic/` — generated reports, HTML, JSON export, campaign summary, campaign CSV
- `docs/API_CONTRACTS.md`, `docs/EVENTS.md`, `docs/STATUS.md`
- `docs/adr/0001-clerk-evidence-provenance-and-radar-handoff.md`
- `docs/schemas/*.schema.json`

### Interfaces added/changed

- `EvidencePackage` schema `1.0.0` (CLERK-owned)
- Report kinds: `single_call`, `multi_call_campaign`, `technical_incident`, `machine_readable_json`
- `GET /clerk/reports` and `POST /clerk/reports/open` as JSON contracts implemented in-process by `RadarReportCatalog`
- Events: `clerk.evidence_package.created`, `clerk.report.ready` (id-only payloads)
- Provisional input schema id `clerk.provisional_upstream.v0` recorded on each package as `upstream_input_schema`

### Tests

`python3 -m pytest` — 33 passed.

Covers schema rejection (duration mismatch, extra fields, relabeled fact class, naive datetimes, confidence bounds), packaging that refuses to drop an orphan observation, report generation from the synthetic fixtures, separation of displayed caller metadata / spoken identifiers / confirmed observations / derived interpretations / campaign attribution, and the RADAR list/open/event adapter.

### Dependencies

- Runtime: `pydantic==2.13.5`
- Tests: `pytest`
- Consumed mocks, because the real schemas are absent: CallSession owner, SHERLOCK observations, WATSON campaigns
- RADAR can import `switchboard.clerk.build_synthetic_catalog` and the models in `switchboard.clerk.schemas.radar`

### Blocking issues

- `ARCHITECTURE.md`, `DATA_MODEL.md`, `SECURITY.md`, and `DECISIONS.md` are absent. CLERK did not invent them. Retention and redaction rules for phone numbers and transcripts in exports are undefined. Events omit that content until a policy exists.
- SHERLOCK observation schema: not in the repo. `ProvisionalObservation` is a mock.
- WATSON campaign schema: not in the repo. `ProvisionalCampaign` is a mock.
- CallSession schema: not in the repo. `ProvisionalCallSession` is a mock.
- No event bus. Events are stored on the in-process catalog.
- RADAR's Vue dashboard is not in the repo. The handoff is the typed adapter and the HTTP-shaped JSON contract only.

### Recommended next work

- SHERLOCK publishes an observation schema. CLERK replaces `ProvisionalObservation` and bumps `schema_version` in a handoff.
- WATSON publishes a campaign schema. CLERK replaces `ProvisionalCampaign` the same way.
- The CallSession owner publishes that schema. CLERK replaces `ProvisionalCallSession`.
- RADAR calls `list_reports` / `open_report` (or the documented HTTP shape once a gateway exists) and renders the returned parts.
- ATLAS publishes security handling for transcripts and caller-ID values inside evidence exports.
