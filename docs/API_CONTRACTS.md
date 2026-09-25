# API contracts

Contract version **0.1.0**. JSON field names are snake_case, ids are UUID strings, and timestamps are timezone-aware ISO-8601. Unknown JSON fields are rejected (`422 invalid_request`).

Pydantic models in `packages/schemas` are the machine-readable source. This file is the behavioral source. OpenAPI from each FastAPI app is generated from the models and is not a second contract.

Error body (`ErrorBody`):

```json
{"error": "call_not_found", "message": "No call session exists with that id."}
```

| Status | `error` | When |
| --- | --- | --- |
| 401 | `webhook_unauthorized` | Carrier signature rejected |
| 401 | `unauthorized` | Missing or wrong internal token |
| 403 | `number_not_enrolled` | `to_e164` is not an active operator number |
| 404 | `call_not_found` | Unknown call session on a read route |
| 404 | `campaign_not_found` | Unknown campaign |
| 422 | `invalid_request` | Body or path failed validation. Values from the body are not echoed |

## Authentication

| Caller | Credential |
| --- | --- |
| Carrier webhook | Provider signature. Mock provider: header `X-Switchboard-Mock-Signature: dev`. Real verifiers land in `packages/telephony` |
| Dev bypass | Honored only when `SWITCHBOARD_ENV=dev` and `SWITCHBOARD_DEV_WEBHOOK_BYPASS=1` together |
| Internal routes | Header `X-Switchboard-Internal-Token` matched against `SWITCHBOARD_INTERNAL_TOKEN` |
| Dashboard | No credential in the skeleton. SENTINEL adds operator auth before any shared deployment |

Internal routes are not published outside the compose network in a real deployment. The local compose file publishes them on localhost so agents can call them.

## apps/api

Base URL locally: `http://localhost:8000`.

### `GET /health`

Response `HealthResponse`: `{"service":"api","status":"ok","version":"0.1.0"}`.

`status: ok` means the process is up. It does not mean Postgres or Redis is reachable.

### `POST /v1/telephony/voice/{provider}`

`provider` is `mock` in 0.1.0. Any other value is `422`.

Request `MockVoiceWebhook`:

```json
{
  "provider_call_id": "demo-1",
  "from_e164": "+15551212000",
  "to_e164": "+15550001001",
  "timestamp": "2026-09-25T20:00:00Z"
}
```

Target behavior:

1. Verify the signature on the raw body before trusting fields.
2. Insert `obs.webhook_receipt` even when the call is rejected.
3. If `to_e164` is not an active `ops.operator_number`, respond `403 number_not_enrolled` and do not issue a token.
4. Insert `obs.call_session` in `ringing` and publish `telephony.call.received`.
5. Issue a stream token and respond `200` with `TelephonyWebhookAck`.

Response:

```json
{
  "call_session_id": "6c0d5a2e-0000-5000-8000-000000000000",
  "instruction": {
    "action": "connect_stream",
    "stream_url": "ws://localhost:8001/v1/streams",
    "stream_token": "<opaque>"
  }
}
```

`VoiceInstruction.action` is `connect_stream`, `hangup`, or `reject`. `stream_url` and `stream_token` are required together for `connect_stream` and forbidden otherwise. The token is not embedded in `stream_url`. The carrier adapter adds `?token=`.

Mock session ids are UUIDv5(`SWITCHBOARD_ID_NAMESPACE`, `mock:{provider_call_id}`).

The voice route performs these five steps. Stream tokens remain the process-local store until `SB-014`. `telephony.call.received` is validated and written with a direct Redis `XADD` (`envelope` JSON, stream `switchboard.events`, approximate maxlen 100000). The shared consumer-group helper remains `SB-016`. A publish failure does not roll back the session. The status route still checks the signature and returns `accepted: true` without a write (`SB-003`). Schema-invalid bodies still fail before the handler (`SB-015`), so they do not insert a receipt.

### `POST /v1/telephony/status/{provider}`

Request `MockStatusWebhook`: `provider_call_id`, `status` (`CallState`), `timestamp`, optional `end_reason`.

Target: update the session and publish `telephony.call.answered`, `telephony.call.completed`, or `telephony.call.failed`. Response `StatusAccepted`: `{"accepted": true}`.

The stub checks the signature and returns `accepted: true` without a write.

### Read models

| Method and path | Success body | Stub |
| --- | --- | --- |
| `GET /v1/calls?limit&cursor` | `CallListResponse` | Empty list, `next_cursor: null` |
| `GET /v1/calls/{call_session_id}` | `CallDetailResponse` | `404 call_not_found` |
| `GET /v1/calls/{call_session_id}/transcript` | `TranscriptListResponse` | `404` |
| `GET /v1/calls/{call_session_id}/findings` | `FindingListResponse` | `404` |
| `GET /v1/calls/{call_session_id}/attributions` | `AttributionListResponse` | `404` |
| `GET /v1/campaigns?limit&cursor` | `CampaignListResponse` | Empty list |
| `GET /v1/campaigns/{campaign_id}` | `Campaign` | `404 campaign_not_found` |

`limit` is an integer from 1 to 200, default 50. `cursor` is an opaque string returned as `next_cursor`.

`CallDetailResponse` carries the layers side by side: `session` and `media_streams` and `transcript` are observations; `turns` and `findings` are interpretations; `attributions` are campaign linkage. Clients must not treat a finding as a transcript.

`CallSessionSummary` is a list-row read model. It is not a fourth stored layer.

### `POST /v1/internal/stream-tokens`

Auth: internal token. Request `IssueStreamTokenRequest`: `{"call_session_id": "<uuid>"}`.

Response `IssueStreamTokenResponse`: `token`, `expires_at`, `stream_url`.

Target store: Redis, TTL 60 seconds, single use, bound to that session. Stub store: process memory, TTL 60 seconds, reusable until expiry, visible only to that API process.

### `POST /v1/internal/stream-tokens/validate`

Auth: internal token. Request `{"token": "<opaque>"}`.

Response `ValidateStreamTokenResponse`: `{"valid": true, "call_session_id": "<uuid>"}` or `{"valid": false, "call_session_id": null}`. An unknown token is `200` with `valid: false`, not `401`. `401` is reserved for the internal credential.

## apps/media_gateway

Base URL locally: `http://localhost:8001`.

### `GET /health`

`HealthResponse` with `service: media_gateway`.

### `WS /v1/streams?token=`

Protocol id: `switchboard.media.v1`.

The gateway calls `POST /v1/internal/stream-tokens/validate` and accepts the socket only when `valid` is true. A missing or rejected token closes with code `1008` before accept. The first server message is `StreamReady`. Frame rules, the PCMU default, the outbound buffer, and barge-in `clear` are specified under [ECHO media requirements](#echo-media-requirements). The socket does not run STT (`SB-005`).

First server message:

```json
{"event": "ready", "protocol": "switchboard.media.v1"}
```

Client JSON messages (`InboundMediaMessage`):

| `event` | Fields |
| --- | --- |
| `start` | `stream_id`, `call_session_id`, `media_format` (`encoding`, `sample_rate_hz`, `channels: 1`) |
| `media` | `sequence`, `timestamp_ms`, `payload_b64` (max 120000 characters) |
| `stop` | optional `reason` |

`encoding` is `audio/pcmu` or `audio/pcm`. A binary WebSocket frame is an audio frame with an implicit sequence. Carrier-native messages are translated in `packages/telephony` before they reach this socket.

Server messages after `ready`: `media`, `mark` (`name`), `clear`. `clear` drops outbound audio still buffered for barge-in. The buffer behavior is specified under ECHO media requirements. The socket sends `ready` on connect and does not synthesize yet (`SB-008`).

Audio bytes, `payload_b64`, and tokens are not logged.

## ECHO media requirements

Owner: ECHO. App: `apps/media_gateway`. This section is the implemented media behavior for contract 0.1.0. The shapes above stay the authority for field names.

### Token validation

On connect, a present `token` query is checked before `accept`:

`POST {API_BASE_URL}/v1/internal/stream-tokens/validate`

Header: `X-Switchboard-Internal-Token` set to `SWITCHBOARD_INTERNAL_TOKEN`.

Body: `{"token":"<opaque>"}`.

`API_BASE_URL` defaults to `http://localhost:8000`. Compose sets `http://api:8000` on the media gateway. `STREAM_TOKEN_VALIDATE_TIMEOUT_S` defaults to 2. A token longer than 256 characters is rejected locally and is not forwarded. The token value is not logged.

| Outcome | Close | Accept |
| --- | --- | --- |
| `token` query missing or empty | `1008` | no |
| Validate call fails, times out, or returns a non-200 or an unreadable body | `1008` | no |
| `valid: false`, or `call_session_id` null | `1008` | no |
| `valid: true` with a call session id | — | yes, then `ready` |

### Parsing `switchboard.media.v1`

Text frames are validated as `InboundMediaMessage`. Unknown fields, unknown `event` values, and the legacy encoding `audio/x-mulaw` fail validation and close `1007`.

| Frame | Rule |
| --- | --- |
| `start` | Once per socket. `call_session_id` must equal the id from token validation. A mismatch closes `1008`. `encoding` is `audio/pcmu` or `audio/pcm`. `channels` is `1`. |
| `media` | After `start`. `payload_b64` is standard base64 with padding. Decoded bytes are one audio frame at the given `sequence`. |
| `stop` | Ends the socket with close `1000`. Valid before `start`. `reason` is not logged. |
| Binary | An audio frame. Allowed after `start`. Sequence is implicit: one greater than the highest sequence already accepted, or `0` when none have been accepted. |

MVP telephony default is `audio/pcmu`, 8000 Hz, mono. `MockTts` emits that default. BELL's carrier parser translates carrier audio to this encoding before the bytes reach the socket.

Audio bytes are counted for the life of the socket and then dropped. They are not written to logs, Redis, or Postgres. STT is not called yet (`SB-005`).

### Outbound buffer and barge-in `clear`

The gateway keeps a per-socket outbound buffer for synthesized audio that has not been written to the carrier yet.

`clear` (`{"event":"clear"}`) drops every byte still in that buffer. That is the barge-in signal. Audio already written on the WebSocket stays written. Audio still queued is not written after `clear`.

This slice does not synthesize on the socket and does not send `clear` from the socket (`SB-008`). `MediaSession.clear_outbound` drops the buffer and returns the `clear` message.

### Mock TTS

`MockTts.synthesize` is local and offline.

| Input | Output |
| --- | --- |
| `""` | `b""` |
| any other string | 160 bytes, one 20 ms `audio/pcmu` frame at 8 kHz mono |

The 160 bytes are SHA-256 of the UTF-8 text, repeated and truncated. The same text always returns the same frame.

### Hot-path timing

`respond_to_audio` runs STT, then `ResponseSelector`, then TTS. It measures each stage with `time.perf_counter` and emits integer milliseconds through `switchboard_observability.log_info`.

Event `hotpath_timing`. Fields: `stt_ms`, plus `select_ms` and `tts_ms` when those stages run. The log line has no transcript text and no audio.

If that emit raises, the gateway logs `hotpath_timing_failed` when the logger still accepts a call, and `respond_to_audio` still returns the audio bytes from TTS.

`MockStt` still returns no text, so the default call returns `b""` after the STT stage. Tests can pass another `SttPort` in-process. The selector remains LOKI's `ResponseSelector`. The WebSocket does not call `respond_to_audio` yet (`SB-008`).

### Waiting

`SB-005` needs this parser and `SB-016`. `SB-008` needs `SB-004`, `SB-005`, `SB-006`, and `SB-007`.

## apps/intelligence

Base URL locally: `http://localhost:8002`.

### `GET /health`

`HealthResponse` with `service: intelligence`.

### `POST /v1/internal/extract`

Auth: internal token. Request `ExtractRequest`: `call_session_id` and `segments` (`TranscriptSegment` objects). Response `ExtractResponse`: `{"findings": []}`.

This route exists so agents can test an extractor without the bus. The production path is the Redis consumer, not this POST. The stub calls `NullFindingExtractor` and returns an empty list. A finding that comes back must cite at least one segment id (`IntelligenceFinding`).

## In-process ports

These are not HTTP APIs.

| Port | Package or module | Owner | Skeleton |
| --- | --- | --- | --- |
| `SignatureVerifier.verify(raw_body, headers)` | `packages/telephony` | BELL | `MockSignatureVerifier` checks the mock header |
| `InstructionRenderer.render(action, stream_url, stream_token)` | `packages/telephony` | BELL | `VoiceInstructionRenderer` builds `connect_stream`, `hangup`, and `reject`. Stream fields follow `VoiceInstruction`. The token is not placed in `stream_url`. `append_stream_token` adds the carrier query |
| `ResponseSelector.select(ResponseRequest) -> ResponseDecision` | `packages/conversation` | LOKI | `FixedResponseSelector` returns "Could you repeat that?" with `strategy_id` `fixed.v1` and confidence `1.0` (certain it followed the rule) |
| `SttPort.push_audio(payload) -> list[SttEvent]` | `apps/media_gateway` | ECHO | `MockStt` returns `[]` |
| `TtsPort.synthesize(text) -> bytes` | `apps/media_gateway` | ECHO | `MockTts` returns one deterministic `audio/pcmu` frame for non-empty text |
| `FindingExtractor.extract(segments)` | `packages/classification` | SHERLOCK | `NullFindingExtractor` returns `[]` |
| `CampaignCorrelator.propose(CorrelationInput)` | `packages/classification` | WATSON | `NullCampaignCorrelator` returns `[]` |

`respond_to_audio` in `apps/media_gateway/switchboard_media/hotpath.py` is the hot-path order: STT, then selector, then TTS. It emits stage durations through `log_info`. The WebSocket handler does not call it yet (`SB-008`).

## Dashboard

The Vue app calls `GET {VITE_API_BASE_URL}/v1/calls` once on load. Default base is `http://localhost:8000`. It uses the TypeScript mirror in `packages/schemas/ts`. It does not open Redis and it does not read Postgres. Live updates in the MVP are polling, owned by RADAR (`SB-013`). There is no dashboard WebSocket in 0.1.0.
