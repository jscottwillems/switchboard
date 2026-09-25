# Frontend data requirements

Contract version **0.1.0**. This is the operator UI's reading of `docs/API_CONTRACTS.md`, `docs/EVENTS.md`, `docs/DATA_MODEL.md`, and `packages/schemas`. It does not add backend fields.

Screens load data only through `OpsDataPort` (`apps/dashboard/src/data/port.ts`). `apps/dashboard/src/data/client.ts` binds that port to the mock adapter. Replacing that export is the switch to HTTP. There is no dashboard WebSocket in 0.1.0.

JSON names are snake_case, matching the TypeScript mirror in `packages/schemas/ts`. Ids the contracts call UUIDs are UUID strings in the fixtures. Timestamps are timezone-aware ISO-8601. Confidence and `stt_confidence` are numbers in `[0, 1]` or null where the contract allows null.

## Routes

| Path | Screen |
| --- | --- |
| `/dashboard/live` | In-progress calls |
| `/dashboard/calls` | Call history |
| `/dashboard/calls/:id` | Call detail |
| `/dashboard/campaigns` | Campaign list |
| `/dashboard/campaigns/:id` | Campaign detail |
| `/dashboard/system` | Process health and operator gauges |
| `/dashboard/reports` | Report index |
| `/dashboard/reports/:reportId` | Open a report |

`/` and `/dashboard` redirect to `/dashboard/live`.

## Port methods and the contract they stand in for

| Port method | Contract route | Mock when missing |
| --- | --- | --- |
| `fetchLiveCalls` | None. Live updates are polling of the read API (`SB-013`). | Sessions with `state: in_progress` |
| `fetchCallHistory` | `GET /v1/calls` → `CallListResponse` | Finished sessions, plus gap columns |
| `fetchCallDetail` | `GET /v1/calls/{id}` → `CallDetailResponse` | `null` stands in for `404 call_not_found` |
| `fetchCampaigns` | `GET /v1/campaigns` → `CampaignListResponse` | `Campaign` plus gap columns |
| `fetchCampaignDetail` | `GET /v1/campaigns/{id}` → `Campaign` | `null` stands in for `404 campaign_not_found` |
| `fetchSystemHealth` | `GET /health` → `HealthResponse` per process | Four `status: ok` rows, plus gap gauges |
| `fetchReportIndex` | None | CLERK-shaped index. See gaps. |
| `openReport` | None | CLERK-shaped body, or `not_found` / `format_unavailable` |

`CallDetailResponse` is `session`, `media_streams`, `transcript`, `turns`, `findings`, `attributions`. The mock adds `events` and `gaps` beside that object. It does not put campaign ids, confidence, or strategy ids onto transcript segments.

## Record layer

Provenance on screen is `RecordLayer`:

| Value | Label | What it is |
| --- | --- | --- |
| `observation` | Observation | Carrier, socket, or recognizer input |
| `interpretation` | Interpretation | A Switchboard method, with confidence |
| `attribution` | Attribution | A campaign link that cites findings |

There is no `unverified` value. Caller signaling can be untrusted and still be an observation (`docs/DATA_MODEL.md`). A claim that is not accepted is an interpretation with `status: proposed`, not a third layer. `stt_confidence` stays on `TranscriptSegment` and is not copied into `IntelligenceFinding.confidence` or `CampaignAttribution.confidence`.

Findings in this catalog are `status: proposed`. `accepted` and `rejected` are in the enum and not used by the fixtures.

## Fields taken from the contracts

### Call session (`CallSession`, observation)

`id`, `operator_number_id`, `external_call_id`, `carrier` (`mock`), `caller_number_e164`, `called_number_e164` (`+15550001001` in the dev seed), `state` (`ringing`, `in_progress`, `completed`, `failed`), `started_at`, `answered_at`, `ended_at`, `end_reason`.

`CallSessionSummary` (the list route) is only `id`, `state`, `caller_number_e164`, `called_number_e164`, `started_at`, `ended_at`. The history table also shows `external_call_id`. That field is on the detail session, not on the summary. See gaps.

The earlier `active` / `abandoned` / `error` statuses are gone. Abandoned and error legs are `failed`, with `end_reason` text. In-progress legs use `in_progress`. This catalog has no `ringing` row.

### Transcript (`TranscriptSegment`, observation)

`id`, `call_session_id`, `media_stream_id`, `sequence`, `speaker` (`caller` or `honeypot`), `source` (`stt` or `tts_input`), `text`, `language`, `start_offset_ms`, `end_offset_ms`, `is_final`, `stt_confidence` (null on `tts_input`), `provider` (`mock-stt` or `mock-tts`), `created_at`.

### Turn (`ConversationTurn`, interpretation)

`id`, `call_session_id`, `turn_index`, `speaker`, `text`, `transcript_segment_ids`, `strategy_id` (`fixed.v1` on honeypot turns, null on caller turns), `confidence`, `created_at`.

The detail page shows the transcript segments. Turns are in the payload so a later adapter can render them without a second shape.

### Finding (`IntelligenceFinding`, interpretation)

`id`, `call_session_id`, `kind`, `value`, `raw_quote`, `transcript_segment_ids` (at least one), `extractor` (`fixture.rule`), `extractor_version` (`0.1.0`), `confidence`, `status`, `created_at`.

`kind` is `callback_number`, `pretext`, `organization_name`, `payment_method`, `url`, `person_name`, or `other`. The old chip kinds (`indicator`, `entity`, `script_phrase`, `tactic`, `amount`, `callback`) are not a contract enum. The generator maps them onto `FindingKind` when it writes fixtures.

### Attribution (`CampaignAttribution`, attribution)

`id`, `campaign_id`, `call_session_id`, `supporting_finding_ids`, `method`, `method_version`, `confidence`, `rationale`, `created_at`.

Unlinked calls have an empty `attributions` array. A call with `gaps.campaign_id` has at least one attribution.

### Campaign (`Campaign`, attribution)

`id`, `label`, `status` (`hypothesized`, `corroborated`, `closed`), `summary`, `created_at`, `updated_at`.

This catalog's three campaigns are `corroborated`. `created_at` is the opened time. `updated_at` is the last-seen time, moved forward to a live `started_at` when that call is in the campaign.

### Media stream (`MediaStream`, observation)

`protocol` is `switchboard.media.v1`. `encoding` is `audio/pcmu`. `state` is `closed` on a finished call and `streaming` on a live call.

### Events

The technical table renders `EventEnvelope` fields: `event_id`, `event_type`, `event_version` (`1`), `occurred_at`, `producer` (`api`, `media_gateway`, `intelligence`), `call_session_id`, `causation_id`, `payload`.

Event names used by the mock:

| `event_type` | Where it shows up |
| --- | --- |
| `telephony.call.answered` | Call timeline and event table |
| `telephony.call.completed` | Finished calls |
| `telephony.call.failed` | Failed calls and synthesis/telephony failures |
| `speech.segment.final` | Recognizer rows |
| `speech.synthesis.completed` | TTS rows |
| `speech.synthesis.failed` | TTS error rows |
| `conversation.response.selected` | Selector rows (was labeled LLM) |
| `conversation.turn.recorded` | Turn rows |
| `intelligence.finding.proposed` | Timeline rows that record a finding |
| `campaign.opened` | First campaign timeline row |
| `campaign.attribution.proposed` | Later campaign timeline rows |

Dialogue-beat rows on the call timeline set `event_type` to null. They are not bus events. Partial transcripts (`speech.segment.partial`) are in the taxonomy and not emitted here. Dashboard polls are not events (`docs/EVENTS.md`).

### Process health (`HealthResponse`)

`service` is `api`, `media_gateway`, `intelligence`, or `dashboard`. `status` is `ok`. `version` is `0.1.0`. `ok` means the process is up.

## Gaps

These are fields the UI renders that `docs/API_CONTRACTS.md` does not return. They live under `gaps` (or on the system page outside `services`). Do not add them to `packages/schemas` from the dashboard.

| Gap | Why the screen wants it | Contract today |
| --- | --- | --- |
| Live board as its own read | `/dashboard/live` needs the set of `in_progress` sessions without waiting for a full history page | No live route. `SB-013` polls `GET /v1/calls`. No WebSocket. |
| `external_call_id` on the list | History shows the carrier id under the timestamp | `CallSessionSummary` omits it. It is on `CallSession` in the detail route. |
| `conversation_state`, `state_transitions` | Dialogue beats (greeting, pretext, payment request, and the rest) | `CallState` is only `ringing`, `in_progress`, `completed`, `failed`. |
| `classification` | Scam-family chip (`irs_impersonation`, `tech_support`, `bank_fraud`, `romance`, `utility_shutoff`, `unknown`) | No classification field on `CallSession` or `Campaign`. |
| `duration_ms` | Duration column | Not stored. A finished call can derive it from `ended_at - started_at`. The column still wants a number for an in-progress row. |
| `engagement_duration_ms` | Time in the pitch, excluding ring | No such column. |
| `campaign_id`, `campaign_label` on a call row | Campaign link from the list and the live rail | The link is `CampaignAttribution`, not a column on the session. The list route does not return attributions. |
| `pipeline` (`stt_ms`, `select_ms`, `tts_ms`, `e2e_ms`, `sampled_at`) | Latency strip. Select is the reply selector. | Not on `CallDetailResponse`. `SB-020` is hot-path timing, not a read model. Display budgets are UI-only. |
| `events[].offset_ms` | Offset column on the event table | `EventEnvelope` has `occurred_at` only. |
| `timeline[]` titles | Operator sentences next to an event name | Payloads are structured models, not a title/detail pair. |
| `paired_reads` | Raw text beside a reading of that text | Observations are transcript rows. Interpretations are turns and findings. The side-by-side block is a view, not a table. `category` (`payment`, `identity`, `threat`, `tooling`, `script`, `callback`, `other`) is not `FindingKind`. |
| `correlation_notes` | Summary line and matched-on chips | `CampaignAttribution` already has `rationale`, `confidence`, `method`, and `supporting_finding_ids`. |
| `key_finding_ids` | Which findings the history row repeats | Not a stored field. |
| Campaign `call_count`, `active_call_count`, `activity` | Volume, sparkline, heatmap | `GET /v1/campaigns/{id}` returns `Campaign` only. |
| Campaign `script_phrases`, `shared_indicators` | Phrase and indicator lists | `IntelligenceFinding` requires `call_session_id` and at least one transcript id. These rows are not findings. |
| Campaign `similarity` | Score and explanation per linked call | No similarity object. |
| Campaign timeline prose | Title and detail next to `campaign.opened` / `campaign.attribution.proposed` | Those events carry `campaign_id`, `label`, `status`, or attribution ids. They do not carry a paragraph. |
| Provider gauges | Name, role (`telephony`, `stt`, `tts`, `selector`), `ok` / `degraded` / `down`, latency | `HealthResponse.status` is only `ok`. |
| Concurrency and cost | Active calls, capacity, queue, dollar split | No route. |
| Error list | Recent warn/error lines | No route. |
| Report index and open | `/dashboard/reports` and `/dashboard/reports/:reportId` | Not in `API_CONTRACTS`. `SB-019` is an evidence manifest with a content hash, not this catalog. |

### Reports

The report mock follows the shapes RADAR already had for a CLERK index (`report_id`, `package_id`, `package_ids`, `kind`, `title`, `synthetic`, `available_formats`) and an open body (`format`, `primary_filename`, `parts[]`). Those names are not in `packages/schemas`.

`openReport` results:

| Status | When |
| --- | --- |
| `opened` | Body includes the parts |
| `not_found` | Unknown `report_id` |
| `format_unavailable` | Format is not in `available_formats` |

Fact-class strings stay visible. The badge is only a display map onto `RecordLayer`:

| `fact_class` | Badge |
| --- | --- |
| `confirmed_observation`, `spoken_identifier`, `reported_caller_metadata`, `raw_observation` | Observation |
| `derived_interpretation` | Interpretation |
| `derived_association` | Attribution |

`reported_caller_metadata` used to render as Unverified. It is an observation now, because the contract has no unverified layer.

### Mock-only fixture fields

| Field | What the adapter does |
| --- | --- |
| `started_offset_sec` | Seconds relative to fetch time. Becomes `session.started_at`. |
| `engagement_delay_ms` | `engagement_duration_ms = duration_ms - engagement_delay_ms` for a live call. |

Live fixture timestamps are stored relative to the Unix epoch so elapsed time stays honest when the app opens later.

## Cross references

- `gaps.campaign_id` links to `/dashboard/campaigns/:id`
- `session.id` links to `/dashboard/calls/:id`
- In-progress detail links to `/dashboard/live?call=:id`
- `CampaignAttribution.campaign_id` links to the campaign
- `similarity.call_id` links to the call. The visible token is `external_call_id`
- `IntelligenceFinding.transcript_segment_ids` point at `TranscriptSegment.id` on that call

Unknown call or campaign ids render an empty state.
