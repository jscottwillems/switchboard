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

Target: the gateway calls `POST /v1/internal/stream-tokens/validate` and accepts the socket only when `valid` is true. The stub accepts any non-empty `token` and closes with code `1008` when `token` is absent. It then sends `StreamReady` and discards further frames. It does not run STT.

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

Server messages after `ready`: `media`, `mark` (`name`), `clear`. `clear` drops outbound audio still buffered for barge-in. ECHO implements that behavior; the stub sends only `ready`.

Audio bytes, `payload_b64`, and tokens are not logged.

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
| `TtsPort.synthesize(text) -> bytes` | `apps/media_gateway` | ECHO | `MockTts` returns `b""` |
| `FindingExtractor.extract(segments)` | `packages/classification` | SHERLOCK | `NullFindingExtractor` returns `[]` |
| `CampaignCorrelator.propose(CorrelationInput)` | `packages/classification` | WATSON | `NullCampaignCorrelator` returns `[]` |

`respond_to_audio` in `apps/media_gateway/switchboard_media/hotpath.py` is the hot-path order: STT, then selector, then TTS. The WebSocket handler does not call it yet.

## Dashboard

The Vue app calls `GET {VITE_API_BASE_URL}/v1/calls` once on load. Default base is `http://localhost:8000`. It uses the TypeScript mirror in `packages/schemas/ts`. It does not open Redis and it does not read Postgres. Live updates in the MVP are polling, owned by RADAR (`SB-013`). There is no dashboard WebSocket in 0.1.0.
