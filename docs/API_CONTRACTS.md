# API contracts

This file records the CLERK contracts for the RADAR handoff. `ARCHITECTURE.md`, `DATA_MODEL.md`, and `SECURITY.md` were not in the repository. Those documents are not invented here.

## CLERK-local mocks

`switchboard.clerk.adapters.upstream` holds provisional inputs used only so packaging can run:

| Mock | Stand-in for | Owner |
| --- | --- | --- |
| `ProvisionalCallSession` | CallSession schema | Not present in this repository |
| `ProvisionalObservation` | Observation schema | SHERLOCK |
| `ProvisionalCampaign` | Campaign schema | WATSON |

Schema id: `clerk.provisional_upstream.v0`. Evidence packages copy that id onto `upstream_input_schema`. These models are not the shared schemas.

## Evidence package

Canonical model: `switchboard.clerk.schemas.evidence.EvidencePackage`.

JSON Schema: [`schemas/evidence_package.schema.json`](schemas/evidence_package.schema.json).

`schema_version` is `1.0.0`. `generator` is `clerk`.

Each claim carries a fact class and an epistemic layer. The pairs are fixed:

| Fact class | Epistemic layer | Meaning |
| --- | --- | --- |
| `reported_caller_metadata` | `raw_observation` | Displayed signaling or caller-ID fields |
| `spoken_identifier` | `raw_observation` | Identifier copied from a transcript excerpt |
| `raw_observation` | `raw_observation` | Source material, or an observation supplied without confirmation |
| `confirmed_observation` | `raw_observation` | Observation supplied with confirmation |
| `derived_interpretation` | `derived_interpretation` | Interpretation supplied as derived |
| `derived_association` | `campaign_attribution` | Campaign link or association reason |

CLERK copies confidence level, score, and basis from the input. It does not derive the level from the score. It does not promote a raw observation to confirmed, and it does not create a campaign link that the input omitted.

`CampaignAssociation.member_call_ids` is the membership list as supplied. `packaged_call_ids` is that list filtered to calls present in the package, in membership order. A call cited by a reason and absent from the package remains in the reason. The package does not treat that absence as a finding.

`CampaignSummary.associated` is false when the package contains no campaign association. That describes the package.

## Report documents

| Kind | Package scope | Human document |
| --- | --- | --- |
| `single_call` | `single_call` | `ReportDocument` |
| `multi_call_campaign` | `campaign` | `ReportDocument` |
| `technical_incident` | `technical_incident` | `ReportDocument` |
| `machine_readable_json` | export of one or more packages | `MachineReadableExport` |

Report id for a package report: `{package_id}__{kind}`.

A human report always includes these sections, in order: provenance legend, call identity, timestamp, displayed caller metadata, call duration, transcript excerpts, spoken identifiers, structured observations, campaign association, association reasons, supporting timestamps, relevant artifacts, confidence levels. A technical incident report inserts `incident_record` immediately after the legend.

Empty sections render `None in source package.` Renderers copy section fields. They do not add call facts.

Output formats:

| Format | Body |
| --- | --- |
| JSON (human report) | `ReportDocument` |
| JSON (`machine_readable_json`) | `MachineReadableExport` (`export_type` `clerk.evidence_export`) |
| Markdown | Structured Markdown |
| PDF-ready | A4 HTML, `text/html; charset=utf-8` |
| CSV | One file per table. Multi-value id cells use a pipe separator. `calls.csv` is the primary file. |
| Campaign summary | `CampaignSummary` JSON |

CSV cells that start with `=`, `@`, tab, or carriage return are prefixed with `'` so spreadsheet tools do not treat them as formulas. Values that start with `+` are left unchanged so displayed numbers stay intact.

## RADAR open-report handoff

Reference adapter: `switchboard.clerk.adapters.radar.RadarReportCatalog`.

This slice does not start an HTTP server and does not define RADAR's screens. A later gateway can expose the same JSON bodies:

### `GET /clerk/reports`

Response: array of `ReportIndexEntry`.

Schema: [`schemas/report_index_entry.schema.json`](schemas/report_index_entry.schema.json).

### `POST /clerk/reports/open`

Request: `OpenReportRequest` (`report_id`, `format`).

Schema: [`schemas/open_report_request.schema.json`](schemas/open_report_request.schema.json).

Response: `OpenReportResponse`.

Schema: [`schemas/open_report_response.schema.json`](schemas/open_report_response.schema.json).

`parts` holds the bytes as text. `primary_filename` names the part a single-document client should show. CSV responses contain one part per table. Other formats contain one part.

`format` values: `json`, `markdown`, `pdf_ready`, `csv`, `campaign_summary`.

The fixture catalog's machine-readable report accepts `json` only. Other formats for that report id are unavailable.

For `kind` `machine_readable_json`, `package_id` is the export id and `package_ids` lists the evidence packages inside the export. The synthetic catalog uses export id `syn-export-synthetic-001`.

Fixture report ids:

- `syn-pkg-call-001__single_call`
- `syn-pkg-campaign-001__multi_call_campaign`
- `syn-pkg-incident-001__technical_incident`
- `syn-export-synthetic-001__machine_readable_json`

```python
from switchboard.clerk import build_synthetic_catalog
from switchboard.clerk.schemas.radar import OpenReportRequest, ReportFormat

catalog = build_synthetic_catalog()
catalog.list_reports()
catalog.open_report(
    OpenReportRequest(
        report_id="syn-pkg-call-001__single_call",
        format=ReportFormat.MARKDOWN,
    )
)
```
