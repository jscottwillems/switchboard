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
| 404 | `call_not_found` | Unknown call session on a read route or a status callback |
| 404 | `campaign_not_found` | Unknown campaign |
| 409 | `state_conflict` | Status callback would move `obs.call_session.state` backward |
| 413 | `webhook_too_large` | Carrier body exceeds 1 MiB. Checked before the signature and before schema validation |
| 422 | `invalid_request` | Body or path failed validation. Values from the body are not echoed |
| 429 | `webhook_rate_limited` | Per-client webhook window exceeded. Checked before schema validation |
| 503 | `dependencies_unavailable` | `GET /health` with `SWITCHBOARD_HEALTH_PROBES=1` and Postgres or Redis refusing TCP |

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

`status: ok` means the process is up. It does not mean Postgres or Redis is reachable unless `SWITCHBOARD_HEALTH_PROBES=1`. With that flag, a refused TCP connection to `DATABASE_URL` or `REDIS_URL` is `503 dependencies_unavailable`. The compose file leaves the flag unset.

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

1. Verify the signature on the raw body before trusting fields. The skeleton does this: size and rate checks, then `MockSignatureVerifier` or the dev bypass, then `MockVoiceWebhook` validation. Invalid JSON with a bad signature is `401`, not `422`.
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

The voice route performs these five steps. Stream tokens remain the process-local store until `SB-014`. `telephony.call.received` is validated and published with `EventBus` (`envelope` JSON, stream `switchboard.events`, approximate maxlen 100000). Only the first insert of a `(carrier, external_call_id)` publishes. A publish failure does not roll back the session. The status route updates that session and publishes `telephony.call.answered`, `telephony.call.completed`, or `telephony.call.failed` through the same `EventBus` (`SB-003`). Schema-invalid bodies still fail before the handler (`SB-015`), so they do not insert a receipt.

### `POST /v1/telephony/status/{provider}`

Request `MockStatusWebhook`: `provider_call_id`, `status` (`CallState`), `timestamp`, optional `end_reason`.

The route verifies the signature on the raw body, then updates the session for that `(provider, provider_call_id)` through `TelephonyObsStore.apply_call_state` (`CallSessionRepository.apply_state`). It publishes through `EventBus.publish` after the commit. The status event id is UUIDv5 of the session id and the event type, so a duplicate callback does not append a second stream entry.

| `status` | Session | Event |
| --- | --- | --- |
| `in_progress` | `in_progress`, `answered_at` = `timestamp` | `telephony.call.answered` |
| `completed` | `completed`, `ended_at` = `timestamp`, `end_reason` when sent | `telephony.call.completed` |
| `failed` | `failed`, `ended_at` = `timestamp`, `end_reason` (`failed` when omitted or blank) | `telephony.call.failed` |
| `ringing` | no write when the session is already `ringing` | none |

Response `StatusAccepted`: `{"accepted": true}`.

A second callback for the same state returns `accepted: true` and leaves `answered_at` and `ended_at` in place. An unknown `provider_call_id` is `404 call_not_found`. A backward transition is `409 state_conflict`. Signature failure is `401 webhook_unauthorized` and does not change the session. A publish failure does not roll back the session. Accepted callbacks, unknown-call callbacks, and signature-rejected JSON objects insert `obs.webhook_receipt` with `event_type` `status`. A rejected signature does not trust `provider_call_id`, so that receipt's `call_session_id` is null.

### Read models

| Method and path | Success body | Current behavior |
| --- | --- | --- |
| `GET /v1/calls?limit&cursor` | `CallListResponse` | Stored sessions, newest `started_at` then `id`. An empty table is `items: []`, `next_cursor: null` |
| `GET /v1/calls/{call_session_id}` | `CallDetailResponse` | Stored layers. Unknown id is `404 call_not_found`. A known id with no child rows returns empty arrays |
| `GET /v1/calls/{call_session_id}/transcript` | `TranscriptListResponse` | Segments for that session, `sequence` ascending. Unknown id is `404 call_not_found` |
| `GET /v1/calls/{call_session_id}/findings` | `FindingListResponse` | Findings for that session. Unknown id is `404 call_not_found` |
| `GET /v1/calls/{call_session_id}/attributions` | `AttributionListResponse` | Attributions for that session. Unknown id is `404 call_not_found` |
| `GET /v1/campaigns?limit&cursor` | `CampaignListResponse` | Empty list |
| `GET /v1/campaigns/{campaign_id}` | `Campaign` | `404 campaign_not_found` |

`limit` is an integer from 1 to 200, default 50. `cursor` is an opaque string returned as `next_cursor`. A cursor that does not decode is `422 invalid_request`. The cursor value is not echoed.

`GET /v1/calls` reads `obs.call_session` through `read_models`. There is no separate live route. `in_progress` rows are in this list. RADAR filters them for the live board (`SB-013`). Detail and the transcript, findings, and attribution routes return `404 call_not_found` when the session id is unknown. A known session with no rows in a layer returns an empty array for that layer. Campaign routes are still the empty stub.

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

The gateway calls `POST /v1/internal/stream-tokens/validate` and accepts the socket only when `valid` is true. A missing or rejected token closes with code `1008` before accept. The first server message is `StreamReady`. Frame rules, the PCMU default, the outbound buffer, and barge-in `clear` are specified under [ECHO media requirements](#echo-media-requirements). The socket passes accepted audio to mock STT and publishes `speech.segment.final` for the fixture frame. A non-empty final calls `respond_to_audio` and publishes `conversation.response.selected` and `conversation.turn.recorded`.

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

Server messages after `ready`: `media`, `mark` (`name`), `clear`. `clear` drops outbound audio still buffered for barge-in. The buffer behavior is specified under ECHO media requirements. After a final, the socket sends synthesized `media`. A later final during outbound sends `clear` before the next reply.

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

Audio bytes are counted for the life of the socket, passed to `SttPort.push_audio`, and then dropped. They are not written to logs, Redis, or Postgres.

### Mock STT

`MockStt.push_audio` is local and offline. It does not decode the samples and it does not call a provider.

| Input | Output |
| --- | --- |
| `MOCK_STT_FIXTURE_FRAME`, 160 bytes of `0xFF` (one 20 ms `audio/pcmu` frame) | One final `SttEvent` |
| any other payload, including empty | `[]` |

That final event has text `fixture caller segment +15551234567`, `is_final` true, `stt_confidence` `1.0`, `start_offset_ms` `0`, and `end_offset_ms` `20`. The trailing token is a literal E.164 so the mock slice can propose `callback_number`. It is not decoded from the PCMU bytes. `stt_confidence` is the mock provider's exact-match score. It is not a Switchboard interpretation confidence.

The socket calls `recognize_frame` for each accepted audio frame. Each final with non-empty text is published as `speech.segment.final` through `switchboard_media.events.event_bus`. `build_envelope` fills `producer: media_gateway`. The payload is `SpeechSegmentPayload` with `speaker: caller` and `is_final: true`. `sequence` starts at `0` on the socket and advances only after a publish that is not `failed`. A Redis failure is `PublishResult.failed`. It does not raise and it does not close the socket. The audio bytes are not fields on the envelope.

### Speak-back

After `recognize_frame` returns one or more non-empty finals, the socket calls `respond_to_audio` with `recognized` set to those finals. `push_audio` is not called again for that frame. The selector is LOKI's `ResponseSelector` (`FixedResponseSelector` by default). TTS is `MockTts`. `turn_index` on that call is the honeypot turn.

The socket then publishes through `event_bus()`:

| Order | Event | Payload |
| --- | --- | --- |
| 1 | `conversation.turn.recorded` | Caller turn. `speaker: caller`, `strategy_id: null`, `confidence: 1.0`, `text` of the last final, `transcript_segment_ids` of every final in the frame. `turn_index` is 0, then 2, then 4 |
| 2 | `conversation.response.selected` | `text`, `strategy_id`, and `confidence` from the `ResponseDecision`. `turn_id` is the honeypot turn |
| 3 | `conversation.turn.recorded` | Honeypot turn. `speaker: honeypot`, same `turn_id` as the selected event, decision `text` / `strategy_id` / `confidence`. `turn_index` is 1, then 3, then 5 |

`causation_id` on the caller turn and the selected event is the speech event id. `causation_id` on the honeypot turn is the selected event id. A failed publish does not raise and does not close the socket. Audio bytes and the reply text are not logged.

Non-empty audio is sent as one or more `media` messages. Outbound `sequence` starts at 0 per socket. `timestamp_ms` is `sequence * 20`. Empty audio sends no `media`. The turn events are still published.

### Outbound buffer and barge-in `clear`

The gateway keeps a per-socket outbound buffer for synthesized audio that has not been written to the carrier yet.

`clear` (`{"event":"clear"}`) drops every byte still in that buffer. That is the barge-in signal. Audio already written on the WebSocket stays written. Audio still queued is not written after `clear`.

If a non-empty final arrives while outbound audio is queued, or already written and not yet cleared, the socket sends `clear` and drops the queue before it writes the new reply. Audio already written stays written. A frame with no final does not send `clear`. `MediaSession.clear_outbound` drops the buffer and returns the `clear` message.

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

`MockStt` returns one final for the fixture frame and `[]` for every other payload, so a non-fixture call to `respond_to_audio` returns `b""` after the STT stage. The fixture frame continues through the selector and TTS inside `respond_to_audio`. Tests can pass another `SttPort` in-process. The selector remains LOKI's `ResponseSelector`. The WebSocket calls `respond_to_audio` with `recognized` set, so the frame is not pushed twice. `recognize_frame` is what publishes `speech.segment.final`.

## apps/intelligence

Base URL locally: `http://localhost:8002`.

### `GET /health`

`HealthResponse` with `service: intelligence`.

### `POST /v1/internal/extract`

Auth: internal token. Request `ExtractRequest`: `call_session_id` and `segments` (`TranscriptSegment` objects). Response `ExtractResponse`: `findings`, an `IntelligenceFinding` list.

This route exists so agents can test an extractor without the bus. The production path is the Redis consumer, not this POST. The route calls `E164FindingExtractor`. A segment whose text contains an E.164 token yields one `proposed` finding of kind `callback_number` citing that segment. A segment without one yields nothing. `NullFindingExtractor` remains the empty port for tests. A finding must cite at least one segment id.

### Extractor consumer

`switchboard_intelligence.extractor_worker` reads consumer group `intelligence.extractor` on `switchboard.events` through `switchboard_intelligence.deps.event_bus`. The loop starts with the intelligence process when `DATABASE_URL` and `REDIS_URL` are set. `SWITCHBOARD_EXTRACTOR_WORKER=0` leaves it off. The extract route above stays available either way.

`speech.segment.final` is adapted to one in-memory `TranscriptSegment` and passed to `FindingExtractor.extract`. The process does not insert `obs.transcript_segment`. Each finding is inserted in `interp.intelligence_finding` and published as `intelligence.finding.proposed`. The proposed event's `confidence` is the finding's confidence. `stt_confidence` stays on the speech payload and is not copied onto the finding.

A final segment with no E.164 inserts nothing and publishes nothing. Any other event type, including `speech.segment.partial` and `telephony.call.completed`, is acknowledged and ignored. An extractor exception is logged with `log_info` as `extractor_failed` and acknowledged. The log fields are the event id, event type, call session id, and a fixed reason. Transcript text and the exception message are not logged. The media socket is a different process and is not closed by that exception.

Finding ids are the UUIDv5 from the extractor. The proposed event id is a UUIDv5 of the finding id, so a redelivery publishes a duplicate rather than a second stream entry. A failed insert is left pending. A failed publish is left pending after the row commit so the same event id can be published again.

### API projector

`switchboard_api.projector` reads consumer group `api.projector` on `switchboard.events` through `switchboard_api.deps.get_event_bus`. The loop starts with the API process when `DATABASE_URL` and `REDIS_URL` are set in the environment. `SWITCHBOARD_PROJECTOR_WORKER=0` leaves it off. Pytest leaves it off unless that flag is `1`.

`speech.segment.final` is inserted as `obs.transcript_segment` with `source: stt` and `provider: mock-stt`. `stt_confidence` is copied onto that row only. The speech payload has no `media_stream_id`. If the call has no `obs.media_stream` yet, the projector inserts one with `external_stream_id` `unscoped`, encoding `audio/pcmu`, and sample rate 8000, and points the segment at it. A stream already stored for the call is reused. `conversation.turn.recorded` is inserted as `interp.conversation_turn`. `conversation.response.selected` is acknowledged and does not insert a row; the honeypot turn is the recorded event.

Telephony events are acknowledged and not inserted again. The voice webhook and the status callback already wrote the session. `speech.segment.partial` is acknowledged and not stored. A failed insert is left pending. Transcript text is not logged.

## In-process ports

These are not HTTP APIs.

| Port | Package or module | Owner | Skeleton |
| --- | --- | --- | --- |
| `SignatureVerifier.verify(raw_body, headers)` | `packages/telephony` | BELL | `MockSignatureVerifier` checks the mock header |
| `InstructionRenderer.render(action, stream_url, stream_token)` | `packages/telephony` | BELL | `VoiceInstructionRenderer` builds `connect_stream`, `hangup`, and `reject`. Stream fields follow `VoiceInstruction`. The token is not placed in `stream_url`. `append_stream_token` adds the carrier query |
| `ResponseSelector.select(ResponseRequest) -> ResponseDecision` | `packages/conversation` | LOKI | `FixedResponseSelector` returns "Could you repeat that?" with `strategy_id` `fixed.v1` and confidence `1.0` (certain it followed the rule) |
| `SttPort.push_audio(payload) -> list[SttEvent]` | `apps/media_gateway` | ECHO | `MockStt` returns one final for the fixture frame and `[]` otherwise |
| `TtsPort.synthesize(text) -> bytes` | `apps/media_gateway` | ECHO | `MockTts` returns one deterministic `audio/pcmu` frame for non-empty text |
| `FindingExtractor.extract(segments)` | `packages/classification` | SHERLOCK | `E164FindingExtractor` proposes `callback_number`. `NullFindingExtractor` returns `[]` |
| `CampaignCorrelator.propose(CorrelationInput)` | `packages/classification` | WATSON | `NullCampaignCorrelator` returns `[]` |

`respond_to_audio` in `apps/media_gateway/switchboard_media/hotpath.py` is the hot-path order: STT, then selector, then TTS. It emits stage durations through `log_info`. The WebSocket calls it after a final, passing the finals from `recognize_frame`.

## Shared clients

These are in-process ports, not HTTP APIs. Call them instead of opening Redis or Postgres ad hoc.

| Port | Module | Use |
| --- | --- | --- |
| `EventBus` | `packages/events` | Publish and consumer-group reads for `switchboard.events`. See `docs/EVENTS.md` |
| `publish_envelope` | `apps/api/switchboard_api/telephony_events.py` | API publisher. Validates, then `EventBus.publish`. Redis failure does not raise |
| `TelephonyObsStore` | `packages/repositories`, bound by `switchboard_api.obs_store.get_obs_store` | Voice webhook: active operator id, idempotent ringing session, webhook receipt |
| `observation_writer` | `packages/repositories` | API projector writes |
| `finding_writer` | `packages/repositories` | Extractor writes. No campaign column |
| `attribution_writer` | `packages/repositories` | Correlator writes |
| `read_models` | `packages/repositories` | Fetch helpers. Call routes use `open_read_models` |

App composition roots are `switchboard_api.deps`, `switchboard_media.events`, and `switchboard_intelligence.deps`. Call list, detail, transcript, findings, and attributions read Postgres. Campaign routes still return the stub bodies.

## Dashboard

The Vue app polls `GET {VITE_API_BASE_URL}/v1/calls` for the live board and the call list, and loads `GET {VITE_API_BASE_URL}/v1/calls/{id}` for detail. Default base is `http://localhost:8000`. During `npm run dev`, an unset base is same-origin and the Vite server proxies `/v1` to `http://127.0.0.1:8000`. `VITE_OPS_DATA=mock` keeps the fixture adapter and does not call the network. The app uses the TypeScript mirror in `packages/schemas/ts`. It does not open Redis and it does not read Postgres. Live updates are polling (`SB-013`), default every 5 seconds (`VITE_LIVE_POLL_MS`). There is no dashboard WebSocket in 0.1.0. Campaign, system, and report screens stay on the mock adapter.
