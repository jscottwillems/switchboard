# ADR 0001 — Evidence provenance and the RADAR handoff

- Status: accepted
- Date: 2026-09-25
- Owner: CLERK

`DECISIONS.md` was not in the repository. This ADR is the CLERK decision for evidence packaging. It does not open a platform-wide decision log.

## Context

Project Switchboard had no code and no shared docs when CLERK started. SHERLOCK's observation schema, WATSON's campaign schema, and the CallSession schema are not in the repo. RADAR's Vue ops dashboard is not in the repo. CLERK still needs a canonical evidence package, report projections, and a typed way for RADAR to open those reports.

## Decision

1. `EvidencePackage` (`schema_version` `1.0.0`) is the canonical CLERK schema.
2. Every claim has a fact class and an epistemic layer. Allowed pairs are fixed in `switchboard.clerk.schemas.provenance`. Reported caller metadata, spoken identifiers, raw observations, confirmed observations, derived interpretations, and campaign attribution cannot be relabeled onto another layer.
3. Human reports, Markdown, PDF-ready HTML, CSV, and campaign summaries are projections of a package. The machine-readable export is the package JSON envelope (`clerk.evidence_export`). Projections copy fields and render `None in source package.` when a section has no rows.
4. Until the owning agents publish their schemas, packaging reads `clerk.provisional_upstream.v0` mocks. Those mocks are not the shared schemas. Packages record the input schema id.
5. RADAR opens reports through `RadarReportCatalog` and the JSON contracts in `docs/API_CONTRACTS.md`. CLERK does not define RADAR's UI and does not start an HTTP server in this slice.
6. Catalog events carry ids only.

## Consequences

Replacing a mock with a real SHERLOCK, WATSON, or CallSession schema is a schema change. It requires a package `schema_version` bump, an update to `API_CONTRACTS.md` / `EVENTS.md`, and a handoff. CLERK will not silently reinterpret another agent's fields.

Confidence values stay as supplied. A later policy for redaction of phone numbers and transcripts in exports belongs to the security doc, which is not written yet. Events already omit that content.
