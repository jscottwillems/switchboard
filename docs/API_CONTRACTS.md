# API contracts

> **DRAFT (BELL bootstrap).** ATLAS owns this document and should refine it. Paths below are what the first slice implements.

Base URL comes from `SWITCHBOARD_PUBLIC_BASE_URL` (default `http://localhost:8000`). Media base comes from `SWITCHBOARD_MEDIA_WS_BASE_URL` (default `ws://localhost:8000`).

The control routes (`/calls/...`) and the media socket are unauthenticated in this slice. Keep them on localhost until SENTINEL adds auth. Carrier webhooks are authenticated by a `WebhookVerifier`.

## Health

`GET /health`

```json
{"status": "ok", "service": "switchboard", "slice": "bell-telephony"}
```

## Webhooks

`POST /webhooks/{provider}/voice`

`POST /webhooks/{provider}/status`

`provider` is `mock` or `twilio`.

Verification runs before a session is created. Failure is HTTP 401 with `{"detail":"webhook signature verification failed"}`. Unknown providers are HTTP 404. Malformed bodies are HTTP 400.

### Mock voice body

`Content-Type: application/json`

Header: `X-Switchboard-Signature: sha256=<hex HMAC-SHA256 of the raw body>`

Secret: `SWITCHBOARD_MOCK_WEBHOOK_SECRET`

```json
{"from": "+15551110000", "to": "+15552220000", "provider_call_id": "mock-call-1", "direction": "inbound"}
```

`provider_call_id` and `direction` are optional. `from` / `to` are required. A fixture is `docs/fixtures/webhooks/mock_inbound.json`.

Success is HTTP 200 JSON:

```json
{
  "call_id": "sb_<hex>",
  "provider_call_id": "mock-call-1",
  "state": "connected",
  "media_stream_url": "ws://localhost:8000/media/stream/mock?call_id=sb_<hex>"
}
```

### Mock status body

```json
{"provider_call_id": "mock-call-1", "status": "failed", "reason": "busy"}
```

`status` maps to completed (`completed`), failed (`failed`, `busy`, `no-answer`, `canceled`), or ignore (`ringing`, `in-progress`, `queued`, `initiated`).

### Twilio voice body

`Content-Type: application/x-www-form-urlencoded` with at least `CallSid`, `From`, and `To`.

Header: `X-Twilio-Signature`

The signature is HMAC-SHA1 over `SWITCHBOARD_PUBLIC_BASE_URL + path` plus sorted decoded form fields, base64-encoded. The public URL must match the URL configured in Twilio exactly.

Success is TwiML:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response><Connect><Stream url="wss://host/media/stream/twilio"/></Connect></Response>
```

Twilio status callbacks use the same signature and the standard `CallSid` / `CallStatus` form.

## Media WebSocket

`WS /media/stream/{provider}`

### Wire format (team lock)

**MVP provider audio is μ-law, 8 kHz, mono.** Both `switchboard.media.v1` (mock) and `twilio.media.v1` use that format on the BELL↔provider socket. Do not put PCM16 or 16 kHz audio on this wire. PCM16 at 16 kHz is ECHO’s internal normalize target only; ECHO converts before returning audio to BELL.

| Field | Wire value |
| --- | --- |
| encoding | `audio/x-mulaw` |
| sample_rate | `8000` |
| channels | `1` |
| payload | raw μ-law bytes, base64-encoded, no WAV header |

Omitted format fields default to that triple. A declared `audio/pcm`, `audio/l16`, sample rate `16000`, or `channels` other than `1` is rejected and does not open or extend the stream. The gateway also drops an outbound pipeline frame that is not this format, so a PCM buffer cannot be forwarded to the carrier by accident.

The fixed reply fixture is `docs/fixtures/audio/fixed_response_mulaw.json`: 20 ms, 440 Hz, 160 bytes, already μ-law. `fixed_response_frame()` synthesizes linear samples only inside that function and converts them before returning.

### switchboard.media.v1 (mock / simulator)

Text JSON frames. One JSON object per WebSocket message.

Client to server:

| type | When | Fields |
| --- | --- | --- |
| `start` | First frame. Binds `call_id` from the voice webhook. | `call_id` (required), optional `stream_id`, `encoding`, `sample_rate`, `channels` |
| `media` | One inbound audio packet. | `sequence`, `timestamp_ms`, `track` (`inbound`), `encoding`, `sample_rate`, `channels`, `payload_b64` |
| `stop` | Stream ended, call still up. | none |
| `hangup` | Caller or simulator hangs up. | optional `reason` (default `caller_hangup`) |

```json
{"type": "start", "call_id": "sb_<hex>"}
{"type": "media", "sequence": 1, "timestamp_ms": 0, "encoding": "audio/x-mulaw", "sample_rate": 8000, "channels": 1, "track": "inbound", "payload_b64": "<base64 mulaw>"}
{"type": "stop"}
{"type": "hangup", "reason": "caller_hangup"}
```

Server to client:

| type | When |
| --- | --- |
| `ready` | After `start`. Carries `call_id`, `stream_id`, `protocol` (`switchboard.media.v1`). |
| `media` | One outbound μ-law packet. `payload_b64` is raw μ-law. `source` is `fixed_response` until ECHO replaces the pipeline. |
| `media_ended` | After `stop` or as part of hangup when a stream was open. |
| `completed` | Local call reached `completed`. |
| `error` | Bad frame, unknown call, or a non-μ-law declaration. `detail` is a short string. |

```json
{"type": "ready", "call_id": "sb_<hex>", "stream_id": "ms_<hex>", "protocol": "switchboard.media.v1"}
{"type": "media", "call_id": "sb_<hex>", "sequence": 1, "encoding": "audio/x-mulaw", "sample_rate": 8000, "channels": 1, "payload_b64": "<base64 mulaw>", "source": "fixed_response"}
{"type": "media_ended", "call_id": "sb_<hex>"}
{"type": "completed", "call_id": "sb_<hex>", "reason": "caller_hangup"}
{"type": "error", "detail": "MVP provider media must be audio/x-mulaw, 8000 Hz, mono"}
```

Payloads must be 1 to 65535 bytes after base64 decoding. A typical telephony frame is 160 bytes (20 ms at 8 kHz). Closing the socket without `hangup` still completes the call.

### twilio.media.v1

Twilio Media Streams JSON. The payload is the same μ-law bytes; the envelope uses Twilio’s `event` names rather than `type`.

| event | BELL behavior |
| --- | --- |
| `connected` | Ignored. |
| `start` | Binds `start.callSid` to the voice-webhook session. `start.mediaFormat` must be `audio/x-mulaw`, sample rate `8000`, channels `1` (or omitted, which means that default). |
| `media` | `media.payload` is base64 μ-law. `media.chunk` is the sequence. `media.track` defaults to `inbound`. |
| `mark` | Ignored. |
| `stop` | Ends the local media stream. Socket close then completes the call. |

Outbound audio is only Twilio’s media event. BELL does not send `ready` or `completed` on this socket:

```json
{"event": "media", "streamSid": "MZ...", "media": {"payload": "<base64 mulaw>"}}
```

`start.start.callSid` correlates the socket to the voice webhook. A `<Connect><Stream>` with no following TwiML ends the carrier leg when the socket closes.

## Call control

`GET /calls/{call_id}` returns:

```json
{"session": {}, "observations": [], "events": []}
```

`session` and `events` use `record_type: "interpretation"`. `observations` use `record_type: "observation"`.

`GET /calls/{call_id}/events`

`GET /calls/{call_id}/status` calls `TelephonyProvider.get_call_status`. Slice 1 returns the local mirror, including `raw_status` when a carrier status was stored.

`POST /calls/{call_id}/forward` body `{"destination":"+15558675309"}`. Destination must be E.164. Mock forwarding is local. Twilio forwarding POSTs TwiML `<Dial>` and requires account SID and auth token (HTTP 503 if missing, HTTP 502 if the carrier update fails).

`POST /calls/{call_id}/terminate` body `{"reason":"operator"}`. Idempotent once the call is completed or failed.

## TelephonyProvider

```text
receive_call(request) -> NormalizedInbound
build_answer(session, media_ws_url) -> ProviderHttpResponse
open_media_stream(session, stream_id, *, encoding, sample_rate) -> MediaStreamHandle
forward_call(session, destination) -> None
terminate_call(session, reason) -> None
get_call_status(session) -> ProviderCallStatus
parse_status_callback(request) -> StatusUpdate
```

`build_answer` and `parse_status_callback` are part of the port because the carrier’s answer body and status form are vendor-specific. The lifecycle still owns state and domain events.

## WebhookVerifier

```text
verify(*, body: bytes, headers, url: str) -> None
```

Raises `WebhookVerificationError` on failure. `MockWebhookVerifier` checks `X-Switchboard-Signature`. `TwilioWebhookVerifier` checks `X-Twilio-Signature` and fails closed when the auth token is empty.

## MediaPipeline (ECHO)

ECHO implements this next. BELL binds `FixedToneMediaPipeline`.

```text
async def handle_inbound(call_id: str, packet: InboundMediaPacket) -> OutboundAudioFrame | None
```

`InboundMediaPacket.payload` is already μ-law 8 kHz mono (`encoding = audio/x-mulaw`, `sample_rate = 8000`, `channels = 1`). ECHO should not parse Twilio or mock JSON. Return an `OutboundAudioFrame` in that same wire format, or `None` to stay silent for that packet. Convert from PCM16 16 kHz inside ECHO before returning; the gateway will not send any other format to the provider.

Wire the replacement in `switchboard.container.build_container` by assigning the pipeline on `MediaGateway`. Domain events stay in the lifecycle; ECHO should not invent parallel call states.

Observations are the raw bytes (`RawObservation`, `record_type = observation`). Events and `CallSession` are interpretations. Speech transcripts, when they exist, must be new interpretation records and must not overwrite the audio observation.
