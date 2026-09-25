# Data model

> **DRAFT (BELL bootstrap).** ATLAS owns this document and should refine it. Slice 1 keeps this state in process memory.

Three record types stay distinct:

| record_type | What it is | Examples |
| --- | --- | --- |
| `observation` | Bytes that arrived, plus envelope facts needed to address them | Webhook body, status body, one media payload |
| `interpretation` | A normalized fact the lifecycle derived | `CallSession`, `CallEvent`, `ProviderCallStatus` |
| `telemetry` | Timing and cost hooks | `TelemetryRecord` |

An observation is not rewritten when a later interpretation changes. A transcript, scam label, or campaign id would be a new interpretation that cites `observation_ids`. This slice does not create those labels.

## CallSession

Internal id `sb_<hex>`. Provider id is stored separately as `provider_call_id` (mock id or Twilio `CallSid`).

Fields: `provider`, `from_number`, `to_number`, `direction` (`inbound` or `outbound`), `state`, timestamps, optional `stream_id`, `media_protocol`, `media_encoding`, `media_sample_rate`, packet counters, `forward_destination`, `failure_reason`, `completion_reason`, `provider_metadata`, `observation_ids`.

`provider_metadata` is a string map of selected carrier fields (for Twilio: account, status, direction, caller name, and city/state/zip/country when present). It is not a copy of the raw webhook. The raw webhook remains on the observation as base64.

States: `received`, `connected`, `media_started`, `media_ended`, `forwarded`, `completed`, `failed`.

## RawObservation

Fields: `observation_id` (`ob_<hex>`), `call_id`, `provider`, `observed_at`, `source` (`webhook`, `status`, or `media`), `content_type`, `raw_b64`, `byte_length`, `sha256`, optional `media`.

`media` is envelope metadata copied from the frame: `sequence`, `timestamp_ms`, `encoding`, `sample_rate`, `track`. It is not a description of what was said.

## CallEvent

See `docs/EVENTS.md`. Ids are `ev_<hex>`.

## Retention

Restarting the process drops sessions, observations, and events. Nothing is written to Postgres. Full audio retention policy is out of scope; the in-memory observation exists so the vertical slice can prove the packet was stored separately from the session.
