# Frontend data requirements

This document lists the fields the Switchboard ops dashboard renders. It is a frontend contract for ATLAS. It does not describe a deployed API, and it does not define shared backend schemas.

The UI loads data only through `OpsDataPort` in `apps/dashboard/src/data/port.ts`. Today `apps/dashboard/src/data/client.ts` binds that port to the mock adapter. A backend adapter should return the same shapes.

## Reads

| Port method | UI |
| --- | --- |
| `fetchLiveCalls()` | `/dashboard/live`, and the live count in the shell |
| `fetchCallHistory()` | `/dashboard/calls` |
| `fetchCallDetail(callId)` | `/dashboard/calls/:id`. Returns `null` when the id is unknown. Live call ids must resolve here too. |
| `fetchCampaigns()` | `/dashboard/campaigns` |
| `fetchCampaignDetail(campaignId)` | `/dashboard/campaigns/:id`. Returns `null` when the id is unknown. |
| `fetchSystemHealth()` | `/dashboard/system` |
| `fetchReportIndex()` | `/dashboard/reports`. Mock of CLERK `GET /clerk/reports`. |
| `openReport(request)` | `/dashboard/reports/:reportId`. Mock of CLERK `POST /clerk/reports/open`. |

Identifiers are strings. Timestamps are ISO-8601 UTC. Durations and offsets are milliseconds. Scores and confidence are `0..1` or `null`.

## Provenance and raw vs derived

Every piece of intelligence carries both:

- `provenance`: `observed` | `inferred` | `unverified`
- `basis`: `raw` | `derived`

They are independent. A spoken badge number can be `raw` and `unverified`. A campaign match is usually `derived` and `inferred`.

The UI always prints the provenance word (Observed / Inferred / Unverified) and the basis word (Raw / Derived). Color is extra, not the only signal.

Structured observations do not use `basis`. They split the two layers:

- `raw`: captured text plus its own provenance
- `interpretation`: a reading of that capture, plus its own provenance, or `null` when nobody has written one

Transcript turns carry provenance only. Unbadged turns are observed speech. `inferred` or `unverified` turns are badged.

## Enums

`Classification`: `irs_impersonation`, `tech_support`, `bank_fraud`, `romance`, `utility_shutoff`, `unknown`

`ConversationState`: `ringing`, `greeting`, `identity_probe`, `pretext`, `urgency`, `payment_request`, `compliance_stall`, `extraction`, `closing`, `ended`

`CallStatus`: `active`, `completed`, `abandoned`, `error`

`CampaignStatus`: `active`, `watching`, `closed`

`IntelligenceKind`: `indicator`, `entity`, `script_phrase`, `tactic`, `amount`, `callback`

`ObservationCategory`: `payment`, `identity`, `threat`, `tooling`, `script`, `callback`, `other`

`Speaker`: `caller`, `honeypot`

`TimelineKind`: `telephony`, `state`, `intel`, `transcript`, `error`

`TechnicalSource`: `telephony`, `stt`, `tts`, `llm`, `orchestrator`

`Severity`: `info`, `warn`, `error`

`ProviderRole`: `telephony`, `stt`, `tts`, `llm`

`ProviderStatus`: `ok`, `degraded`, `down`

## Shared objects

### ClassifiedValue

| Field | Type | UI |
| --- | --- | --- |
| `label` | Classification | Classification text |
| `provenance` | Provenance | Badge next to the classification |
| `confidence` | number or null | Percent next to the badge. Hidden when null. |

### IntelligenceItem

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | List key |
| `kind` | IntelligenceKind | Small kind label on detail rows |
| `label` | string | Chip and row title |
| `value` | string | Row body |
| `provenance` | Provenance | Badge |
| `basis` | IntelligenceBasis (`raw` or `derived`) | Raw / Derived mark |
| `confidence` | number or null | Percent. Hidden when null. |
| `evidenceTurnIds` | string[] | Not drawn yet. Kept so a later UI can jump to turns. Ids must exist on that call's transcript when the item belongs to a call. Campaign-level items may use an empty array. |

### TranscriptTurn

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | List key |
| `speaker` | Speaker | Caller or Honeypot column |
| `text` | string | Turn text |
| `offsetMs` | number | Clock offset from answer |
| `provenance` | Provenance | Badge when not `observed` |

### PipelineLatency

| Field | Type | UI |
| --- | --- | --- |
| `sampledAt` | string | "Sampled …" caption |
| `sttMs` | number | STT meter |
| `llmMs` | number | LLM meter |
| `ttsMs` | number | TTS meter |
| `e2eMs` | number | End-to-end meter. Latest turn, time to first audio. |

Display budgets (800 / 1200 / 700 / 2500 ms) are UI-only. Do not send them.

### ActivityBucket

| Field | Type | UI |
| --- | --- | --- |
| `day` | `YYYY-MM-DD` | Heatmap row and list sparkline |
| `hour` | integer 0–23 UTC | Heatmap column |
| `count` | integer | Cell intensity and daily totals |

Missing hours are treated as zero. `callCount` on a campaign must equal the sum of its buckets.

## LiveCall

Returned by `fetchLiveCalls`. Sorted oldest-first by the UI's current mock; the screen does not depend on order beyond stable selection.

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | Record link, query `?call=` |
| `startedAt` | string | Elapsed time is `now - startedAt`, ticked locally |
| `callerNumberMasked` | string | Rail and header |
| `status` | literal `active` | Status pill |
| `conversationState` | ConversationState | State pill |
| `stateProvenance` | Provenance | Badge on the state pill. Provenance of the committed state. |
| `classification` | ClassifiedValue | Classification row |
| `campaignId` | string or null | Link target |
| `campaignName` | string or null | Link text. Null when `campaignId` is null. |
| `transcript` | TranscriptTurn[] | Live transcript |
| `intelligence` | IntelligenceItem[] | Extracted intelligence |
| `pipeline` | PipelineLatency | Latency strip |

The same id must be returned by `fetchCallDetail`.

## CallSummary

Returned by `fetchCallHistory`, and embedded as `CampaignDetail.relatedCalls`.

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | Link to `/dashboard/calls/:id` |
| `startedAt` | string | History timestamp |
| `endedAt` | string or null | Detail "Ended". Null while the call is up. |
| `durationMs` | number | Duration column. For active calls this is the duration at fetch time. The detail page ticks elapsed from `startedAt` instead of trusting this number after load. |
| `engagementDurationMs` | number | Engagement column. Time the caller stayed in the pitch, excluding ring time. Must be `<= durationMs` for a finished call. For an active call it is the value at fetch time. |
| `status` | CallStatus | Status pill |
| `callerNumberMasked` | string | Caller column |
| `conversationState` | ConversationState | Current or last substantive state. Finished calls keep the state they reached; `status` says whether the leg ended. |
| `stateProvenance` | Provenance | Badge on that state |
| `classification` | ClassifiedValue | Classification column |
| `campaignId` | string or null | Campaign link |
| `campaignName` | string or null | Campaign link text |
| `keyIndicators` | IntelligenceItem[] | Indicator column. These ids must also appear in `CallDetail.intelligence`. |

History rows in the mock are finished (`completed`, `abandoned`, or `error`), not `active`. Active calls are on the live board and still have detail records.

## CallDetail

`CallSummary` plus:

| Field | Type | UI |
| --- | --- | --- |
| `intelligence` | IntelligenceItem[] | Extracted intelligence section |
| `pipeline` | PipelineLatency | Latency strip |
| `timeline` | TimelineEntry[] | Call timeline |
| `transcript` | TranscriptTurn[] | Transcript section |
| `stateTransitions` | StateTransition[] | State section |
| `observations` | StructuredObservation[] | Raw vs interpretation |
| `correlation` | CorrelationReasoning[] | Correlation section |
| `technicalEvents` | TechnicalEvent[] | Technical table |

### TimelineEntry

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | List key |
| `at` | string | Not shown as an absolute clock today; available for a future axis |
| `offsetMs` | number | Offset label |
| `kind` | TimelineKind | Kind pill |
| `title` | string | Title |
| `detail` | string | Supporting line |

### StateTransition

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | List key |
| `at` | string | Reserved. The screen shows `offsetMs`. |
| `offsetMs` | number | Offset label |
| `from` | ConversationState or null | Left side of the arrow. Null on the first transition. |
| `to` | ConversationState | Right side of the arrow |
| `reason` | string | Why the state changed |
| `provenance` | Provenance | Badge |

The chain must be contiguous: the first `from` is null, and each later `from` equals the previous `to`. The last `to` is `conversationState`. The last `provenance` is `stateProvenance`.

### StructuredObservation

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | List key |
| `at` | string | Reserved |
| `offsetMs` | number | Offset label |
| `category` | ObservationCategory | Category pill |
| `raw.text` | string | Raw observation column |
| `raw.provenance` | Provenance | Badge on the raw column |
| `interpretation` | `{ text, provenance }` or null | Interpretation column, or "No interpretation recorded." |
| `interpretation.text` | string | Interpretation body |
| `interpretation.provenance` | Provenance | Badge on the interpretation column |

### CorrelationReasoning

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | List key |
| `campaignId` | string or null | Link. Null means the call stayed unlinked. |
| `campaignName` | string or null | Link text |
| `score` | number 0..1 | Percent and bar |
| `summary` | string | Title |
| `explanation` | string | Reasoning paragraph |
| `provenance` | Provenance | Badge on the reasoning itself |
| `matchedOn[].label` | string | Chip text |
| `matchedOn[].provenance` | Provenance | Badge on that chip |

### TechnicalEvent

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | Row key |
| `at` | string | Reserved |
| `offsetMs` | number | Offset column |
| `source` | TechnicalSource | Source column |
| `severity` | Severity | Severity pill |
| `message` | string | Message |
| `attributes[].key` | string | Attribute name |
| `attributes[].value` | string | Attribute value |

Attributes are strings so the UI does not guess types. Put numbers in the string if an operator needs to see them.

## CampaignSummary

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | Link to `/dashboard/campaigns/:id` |
| `name` | string | Card title |
| `status` | CampaignStatus | Status pill |
| `classification` | ClassifiedValue | Classification on the card |
| `firstSeenAt` | string | Detail stat |
| `lastSeenAt` | string | Card and detail |
| `callCount` | number | Aggregate answered calls. Equals the sum of `activity[].count`. |
| `activeCallCount` | number | Calls currently on the live board for this campaign |
| `summary` | string | Card and detail lede |
| `topIndicators` | IntelligenceItem[] | Chips on the list card. The mock copies the first three `sharedIndicators`. A list payload can send them directly. |
| `activity` | ActivityBucket[] | Daily sparkline on the list. The client rolls hours up by `day`. |

## CampaignDetail

`CampaignSummary` plus:

| Field | Type | UI |
| --- | --- | --- |
| `timeline` | CampaignTimelineEntry[] | Campaign timeline |
| `relatedCalls` | CallSummary[] | Related-call table. May be a sample, smaller than `callCount`. |
| `commonScriptPhrases` | IntelligenceItem[] | Phrase list |
| `sharedIndicators` | IntelligenceItem[] | Indicator list |
| `similarity` | CampaignSimilarity[] | Score, explanation, link to the call |

### CampaignTimelineEntry

| Field | Type | UI |
| --- | --- | --- |
| `id` | string | List key |
| `at` | string | Absolute timestamp |
| `title` | string | Title |
| `detail` | string | Supporting line |

### CampaignSimilarity

| Field | Type | UI |
| --- | --- | --- |
| `callId` | string | Link. Must be one of `relatedCalls`. |
| `score` | number 0..1 | Percent and bar |
| `explanation` | string | Why this call sits in the campaign |
| `provenance` | Provenance | Badge on the explanation |

## SystemHealth

| Field | Type | UI |
| --- | --- | --- |
| `sampledAt` | string | Sample caption |
| `providers[].id` | string | Row key |
| `providers[].name` | string | Provider name |
| `providers[].role` | ProviderRole | Role column |
| `providers[].status` | ProviderStatus | OK / Degraded / Down |
| `providers[].latencyMs` | number | Latency column |
| `providers[].detail` | string | Detail |
| `latency.sttMs` | number | Same latency strip as a call |
| `latency.llmMs` | number | |
| `latency.ttsMs` | number | |
| `latency.e2eMs` | number | |
| `concurrency.activeCalls` | number | Numerator |
| `concurrency.capacity` | number | Denominator. Must be `> 0` for the bar. |
| `concurrency.queueDepth` | number | Queue caption |
| `cost.windowLabel` | string | Window caption, e.g. `Last 24 hours` |
| `cost.currency` | literal `USD` | Formatter |
| `cost.stt` | number | Dollars |
| `cost.tts` | number | Dollars |
| `cost.llm` | number | Dollars |
| `cost.telephony` | number | Dollars |
| `errors[].id` | string | List key |
| `errors[].at` | string | Timestamp |
| `errors[].source` | string | Free-text source, not the provider enum |
| `errors[].severity` | `warn` or `error` | Pill |
| `errors[].message` | string | Body |

The UI sums `cost.stt + cost.tts + cost.llm + cost.telephony`. No total field is required.

## Mock-only fields

These exist in fixture files so elapsed time stays honest when the app is opened later. The port does not expose them.

| Fixture field | File | What the adapter does |
| --- | --- | --- |
| `startedOffsetSec` | `live-calls.json` | Negative seconds from fetch time. Becomes `startedAt`. |
| `engagementDelayMs` | `live-detail-extras.json` | `engagementDurationMs = durationMs - engagementDelayMs` at fetch time. |
| `relatedCallIds` | `campaign-details.json` | Joined to `CallSummary` records as `relatedCalls`. |

Live detail sections store `offsetMs` without `at`. The adapter stamps `at` from `startedAt + offsetMs`.

`lastSeenAt` in the campaign fixture is a baseline. The adapter moves it forward to the newest live `startedAt` for that campaign so the card does not sit behind the clock. A backend should send the real last-seen time.

## Cross references the UI follows

- `LiveCall.campaignId` and `CallSummary.campaignId` link to `/dashboard/campaigns/:id`
- `CallDetail` and campaign related calls link to `/dashboard/calls/:id`
- Active detail records link back to `/dashboard/live?call=:id`
- `CorrelationReasoning.campaignId` links to the campaign
- `CampaignSimilarity.callId` links to the call
- `IntelligenceItem.evidenceTurnIds` point at `TranscriptTurn.id` on that call

Unknown call or campaign ids render an empty state. They should not be linked from fixtures.

## CLERK reports

These shapes are copied from CLERK `docs/schemas/report_index_entry.schema.json`, `open_report_request.schema.json`, and `open_report_response.schema.json` on `cursor/clerk-evidence-packages-cdef`. The dashboard mocks the JSON. It does not install the Python package and it does not add a server.

Fixture report ids:

- `syn-pkg-call-001__single_call`
- `syn-pkg-campaign-001__multi_call_campaign`
- `syn-pkg-incident-001__technical_incident`
- `syn-export-synthetic-001__machine_readable_json`

Human reports offer `json`, `markdown`, `pdf_ready`, `csv`, and `campaign_summary`. The machine-readable report offers `json` only. The format picker defaults to `markdown` when that format is available, otherwise the first available format.

`openReport` returns a frontend result, not a third CLERK schema:

| Status | When |
| --- | --- |
| `opened` | Body is `OpenReportResponse` |
| `not_found` | Unknown `report_id` |
| `format_unavailable` | Format is not in that report's `available_formats` |

### ReportIndexEntry

| Field | Type | UI |
| --- | --- | --- |
| `report_id` | string | Link and detail id |
| `package_id` | string | Package column. Export id when `kind` is `machine_readable_json`. |
| `package_ids` | string[] | Not drawn on the list. Present on the open response. |
| `kind` | `single_call` \| `multi_call_campaign` \| `technical_incident` \| `machine_readable_json` | Kind column |
| `title` | string | Link text |
| `synthetic` | boolean | Synthetic pill when true |
| `available_formats` | ReportFormat[] | Format column and the picker |

`ReportFormat`: `json`, `markdown`, `pdf_ready`, `csv`, `campaign_summary`.

### OpenReportRequest

| Field | Type | UI |
| --- | --- | --- |
| `report_id` | string | Route param |
| `format` | ReportFormat | Format picker and `?format=` |

### OpenReportResponse

| Field | Type | UI |
| --- | --- | --- |
| `report_id` | string | Header |
| `package_id` | string | Header |
| `package_ids` | string[] | Not drawn in this slice |
| `kind` | ReportKind | Header |
| `format` | ReportFormat | Matches the picker |
| `synthetic` | boolean | Inherited from the index row |
| `primary_filename` | string | File marked primary. CSV primary is `calls.csv`. |
| `parts[].filename` | string | Part picker when there is more than one part |
| `parts[].content_type` | string | Caption. `application/json` and `text/csv` / `text/markdown` / `text/html` as CLERK specifies |
| `parts[].body` | string | Text body. JSON parts are parsed for the fact-class view |

Only `csv` has more than one part. Other formats have one part.

### Fact class badges

When a JSON part is shown, each object with a `fact_class` string gets a provenance badge. The fact-class token and, when present, `epistemic` stay visible. This map is display-only:

| CLERK `fact_class` | Badge |
| --- | --- |
| `confirmed_observation` | Observed |
| `spoken_identifier` | Observed |
| `reported_caller_metadata` | Unverified |
| `raw_observation` | Unverified |
| `derived_interpretation` | Inferred |
| `derived_association` | Inferred |

Markdown, CSV, and PDF-ready HTML are shown as text. They are not re-badged.

## What this slice does not need

- Authentication payloads
- Audio URLs or recording binaries
- Writable campaign actions
- A websocket frame format

If live updates arrive later, the same `LiveCall` object can be pushed. The screen already recomputes elapsed time from `startedAt`.
