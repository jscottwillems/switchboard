# Events

> **DRAFT (BELL bootstrap).** ATLAS owns this document and should refine it. The names below are the slice 1 contract.

Domain events are interpretations (`record_type: "interpretation"`). They are not telemetry, and they are not the raw webhook or audio bytes. Those bytes are `RawObservation` records (`record_type: "observation"`).

An in-process bus publishes each domain event. The telemetry subscriber writes a structured log and an in-memory `TelemetryRecord` (`record_type: "telemetry"`). `estimated_cost_usd` is always null until a rate card exists. Packet telemetry uses separate names, `media.packet.observed` and `media.packet.sent`, so per-packet cost hooks do not pretend to be domain events.

## Names

| Name | When |
| --- | --- |
| `call.received` | Inbound webhook normalized and the session stored. |
| `call.connected` | The answer response (mock JSON or TwiML) is ready to return. |
| `call.media.started` | A media stream is bound to the session. |
| `call.media.ended` | The stream stops, or hangup/failure ends an open stream. |
| `call.forwarded` | `forward_call` succeeded. Media is ended first if it was open. |
| `call.completed` | Local hangup, socket disconnect, or a completed status callback. |
| `call.failed` | Carrier failure status, or a vendor side effect failed. |

Terminal states are `completed` and `failed`. A second hangup does not emit another `call.completed`.

## Payload shape

```json
{
  "record_type": "interpretation",
  "event_id": "ev_<hex>",
  "name": "call.received",
  "occurred_at": "2026-09-25T20:00:00Z",
  "call_id": "sb_<hex>",
  "provider": "mock",
  "elapsed_ms": 0,
  "data": {}
}
```

`elapsed_ms` is measured from session creation. `data` fields:

| Event | data |
| --- | --- |
| `call.received` | `provider_call_id`, `from_number`, `to_number`, `direction` |
| `call.connected` | `provider_call_id` |
| `call.media.started` | `stream_id`, `protocol` |
| `call.media.ended` | `stream_id`, `packets_observed`, `packets_sent` |
| `call.forwarded` | `destination` |
| `call.completed` | `reason` |
| `call.failed` | `reason` |

Fixtures for every name are in `docs/fixtures/events/`. A telemetry example is `docs/fixtures/telemetry/call.completed.json`.

## Simulator sequence

A successful `python -m switchboard.simulator` run emits, in order:

1. `call.received`
2. `call.connected`
3. `call.media.started`
4. `call.media.ended`
5. `call.completed` with `data.reason = "caller_hangup"`

The inbound audio packet is an observation and a `media.packet.observed` telemetry record. It does not add a domain event.

## State machine

```text
received -> connected -> media_started -> media_ended -> completed
                     -> forwarded -> completed
                     -> completed
                     -> failed
media_started -> failed   (emits call.media.ended first)
```

`webhook.inbound` and `webhook.status` telemetry records carry `duration_ms` for the handler. Domain events carry `elapsed_ms` from session creation. Logs are JSON on the `switchboard` logger and include a `telemetry` object when the line is a metric.
