# Status

> **DRAFT (BELL bootstrap).** ATLAS owns this document and should refine it. The handoff below is the slice 1 record for ECHO.

The telephony vertical slice is implemented on one FastAPI process: signed webhook, `CallSession`, media WebSocket, fixed-tone reply, hangup, mock simulator, and a Twilio adapter. Dashboard, speech, and campaign correlation are not in this repo yet.

## HANDOFF — BELL — 2026-09-25T20:38:23Z

Completed:
- TelephonyProvider port with receive_call, open_media_stream, forward_call, terminate_call, and get_call_status, plus provider-specific answer and status parsing.
- MockTelephonyProvider and TwilioTelephonyProvider. Twilio uses TwiML, Media Streams framing, and Calls REST updates without a vendor SDK. Lifecycle and routes do not import Twilio.
- WebhookVerifier boundary: MockWebhookVerifier (HMAC-SHA256 test payloads) and TwilioWebhookVerifier (HMAC-SHA1, fail closed without a token).
- Call lifecycle received → connected → media started/ended → completed/failed, plus forwarded. Per-call locks and duplicate provider call ids.
- Media WebSocket observes inbound packets as RawObservation records and returns a fixed 20 ms μ-law tone (switchboard.media.v1 and twilio.media.v1).
- Disconnect and explicit hangup. Concurrent calls covered by lifecycle and simulator tests.
- Domain events: call.received, call.connected, call.media.started, call.media.ended, call.forwarded, call.completed, call.failed.
- Structured telemetry with elapsed and handler timing. estimated_cost_usd is null until a rate card exists.
- Local simulator CLI, pytest, Docker Compose API-only, draft contracts, JSON fixtures.
- In-memory sessions (ADR-001). Postgres and Redis are not running.

Files changed:
- README.md, pyproject.toml, Dockerfile, docker-compose.yml, .env.example, .gitignore, .dockerignore
- switchboard/ package (app, providers, verifiers, lifecycle, media gateway, simulator)
- tests/ for the simulator path, Twilio adapter, signatures, and contracts
- docs/ARCHITECTURE.md, docs/API_CONTRACTS.md, docs/EVENTS.md, docs/DATA_MODEL.md, docs/SECURITY.md, docs/DECISIONS.md, docs/STATUS.md, docs/TELEPHONY.md
- docs/fixtures/events/*.json, docs/fixtures/webhooks/mock_inbound.json, docs/fixtures/media/*.json, docs/fixtures/telemetry/call.completed.json

Interfaces added/changed:
- TelephonyProvider and WebhookVerifier (docs/API_CONTRACTS.md).
- CallSession, CallEvent, RawObservation, TelemetryRecord (docs/DATA_MODEL.md, docs/EVENTS.md).
- Media websocket protocols switchboard.media.v1 and twilio.media.v1.
- MediaPipeline.handle_inbound(call_id, InboundMediaPacket) -> OutboundAudioFrame | None. FixedToneMediaPipeline is the current binding.

Tests:
- pytest covers signed webhook → session → media observe → fixed reply → hangup, bad signatures, forward, status failure, disconnect, concurrent in-memory sessions, Twilio TwiML plus media frames, and the simulator CLI against a live uvicorn process.

Dependencies:
- Python 3.12, FastAPI, Pydantic v2, uvicorn, httpx, websockets. No Twilio SDK, Redis, or Postgres.

Blocking issues:
- None for the local simulator path.
- Before any non-local deploy, SENTINEL should authenticate the media WebSocket and the /calls control API. Webhook verification is already a separate boundary.
- get_call_status mirrors local state and does not poll Twilio REST yet.

Recommended next work:
- ECHO: implement MediaPipeline in place of FixedToneMediaPipeline. Consume InboundMediaPacket (already de-framed). Return 8 kHz μ-law OutboundAudioFrame payloads, or None to send silence. Do not parse Twilio or mock JSON in the speech pipeline; SwitchboardMediaFramer and TwilioMediaFramer stay on the BELL side of the socket.
- ECHO: keep transcripts and other speech products as new interpretation records that cite RawObservation ids. Do not overwrite observation bytes or reuse the call.* event names for partial transcripts.
- ECHO: the gateway calls handle_inbound once per inbound packet and ships the returned frame back on the open socket. Start with that single-frame contract before streaming multi-frame TTS.

### Interfaces ECHO must implement next

1. `MediaPipeline.handle_inbound(call_id: str, packet: InboundMediaPacket) -> OutboundAudioFrame | None` in the role of `switchboard.media.pipeline.MediaPipeline`.
2. Outbound frames are `audio/x-mulaw`, 8000 Hz, mono. The current tone is 160 bytes (20 ms) from `fixed_response_frame()`; ECHO may return a different length within the 1–65535 byte gateway limit.
3. Optional later: subscribe to the in-process `EventBus` for `call.media.started` and `call.media.ended` if the speech pipeline needs stream lifetime. Publishing new `call.*` names is not part of this contract.
