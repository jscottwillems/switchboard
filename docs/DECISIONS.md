# Decisions

> **DRAFT (BELL bootstrap).** ATLAS owns this document and should refine it.

## ADR-001 — In-memory sessions for slice 1

Status: accepted for the first vertical slice.

The call path needs a session store, not a durable warehouse. An in-process store (`InMemorySessionStore`) keeps the simulator and pytest free of Redis and Postgres. Docker Compose starts only the API.

Consequences: a restart drops live calls; one process owns all sockets; horizontal scale is a later decision. The store is behind `CallLifecycle`, so a Redis implementation can replace it without rewriting providers. Postgres remains the likely home for durable observations once ECHO and campaign correlation need them. It is not on the media hot path yet.

## ADR-002 — TelephonyProvider, Twilio first, mock for local

Status: accepted.

Business logic depends on `TelephonyProvider` and `WebhookVerifier`. `TwilioTelephonyProvider` speaks TwiML, Media Streams JSON, and the Calls REST update without the Twilio SDK, so the dependency stays an adapter. `MockTelephonyProvider` speaks JSON and `switchboard.media.v1` so the vertical slice runs with no carrier account.

`get_call_status` returns the local session mirror. A later change can refresh from the carrier REST API behind the same method.

`terminate_call` on Twilio is best-effort: with credentials it sets the call status to completed; without credentials it no-ops because closing the media socket ends a `<Connect><Stream>` verb that has no following TwiML. `forward_call` cannot no-op, so missing credentials are HTTP 503.

## ADR-003 — MediaPipeline is ECHO’s port

Status: accepted.

The gateway normalizes vendor frames to `InboundMediaPacket` and sends `OutboundAudioFrame` bytes back through the framer. `FixedToneMediaPipeline` returns one known 20 ms μ-law tone so the path is testable before speech services exist. ECHO replaces that class. ECHO does not need to reimplement Twilio framing.

## ADR-004 — Observations stay raw

Status: accepted.

Webhook and audio bytes are stored as `RawObservation` (`record_type: observation`). `CallSession` and `CallEvent` are `interpretation`. Telemetry is a third record type. Later analysis must append interpretations that cite observation ids rather than rewriting the bytes or overloading domain events.

## ADR-005 — Single process, no extra services

Status: accepted for slice 1.

The repo is one Python package. There is no frontend app, worker fleet, or message bus beyond the in-process `EventBus`. New services wait until a slice needs them.

## ADR-006 — Provider media wire is μ-law 8 kHz mono

Status: team lock from ECHO. Do not change without ATLAS.

The MVP media WebSocket, for both the mock provider and Twilio Media Streams, carries `audio/x-mulaw` at 8000 Hz, 1 channel. Payloads are raw μ-law bytes, base64-encoded, with no WAV header. PCM16 at 16 kHz is ECHO’s internal normalize target and is not a BELL↔provider wire format.

The fixed tone is converted to μ-law before it is sent. `docs/fixtures/audio/fixed_response_mulaw.json` is that wire buffer. Declared PCM or 16 kHz frames are rejected.
