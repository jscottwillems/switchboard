# Events

This file records CLERK events. No event bus is implemented. `RadarReportCatalog.events()` returns the events recorded while reports are published. Payloads are identifier-only: they carry package ids, report ids, kinds, formats, the synthetic flag, and `occurred_at`. Transcript text, caller-ID values, and observation statements stay in the evidence package.

Schema: [`schemas/clerk_event.schema.json`](schemas/clerk_event.schema.json).

## `clerk.evidence_package.created`

Emitted when an evidence package is published to the catalog.

| Field | Value |
| --- | --- |
| `event_type` | `clerk.evidence_package.created` |
| `occurred_at` | Package `generated_at` |
| `synthetic` | Package flag |
| `package_id` | Evidence package id |
| `package_ids` | `[package_id]` |
| `report_id` | absent |
| `report_kind` | absent |
| `available_formats` | empty |

## `clerk.report.ready`

Emitted when a report can be opened through the RADAR handoff.

| Field | Value |
| --- | --- |
| `event_type` | `clerk.report.ready` |
| `occurred_at` | Package or export `generated_at` |
| `synthetic` | Report flag |
| `package_id` | Evidence package id, or the export id for `machine_readable_json` |
| `package_ids` | Packages a client can open from this report |
| `report_id` | Id accepted by `POST /clerk/reports/open` |
| `report_kind` | `single_call`, `multi_call_campaign`, `technical_incident`, or `machine_readable_json` |
| `available_formats` | Formats `open_report` will serve |

Publishing the machine-readable export emits `clerk.report.ready` and does not emit another `clerk.evidence_package.created`. The export references packages that already have created-events.

The synthetic catalog emits three package-created events and four report-ready events (three human reports and one export).
