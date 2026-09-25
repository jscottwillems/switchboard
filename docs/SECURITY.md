# Security

> **DRAFT (BELL bootstrap).** ATLAS owns this document and should refine it. SENTINEL owns production hardening of the boundaries below.

This slice is a defensive honeypot for numbers the operator controls. It is not a tool for placing calls to third parties, intercepting numbers the operator does not own, or bypassing a carrier’s authentication.

## Webhook verification

Every inbound voice and status request passes through a `WebhookVerifier` before `receive_call` or `parse_status_callback`. Routes do not implement signature algorithms themselves.

| Provider | Header | Algorithm |
| --- | --- | --- |
| mock | `X-Switchboard-Signature` | `sha256=` + hex HMAC-SHA256 of the raw body, key `SWITCHBOARD_MOCK_WEBHOOK_SECRET` |
| twilio | `X-Twilio-Signature` | Base64 HMAC-SHA1 of the exact public URL plus sorted decoded form fields, key `SWITCHBOARD_TWILIO_AUTH_TOKEN` |

Comparisons use `hmac.compare_digest`. Missing Twilio credentials fail closed (401). An empty mock secret also fails closed. The default mock secret `dev-mock-secret` logs a warning at startup and is only for localhost.

Known test vector (mock):

- secret: `test-secret`
- body: `{"ping":"pong"}`
- header: `sha256=39773dd05dd0bf0e0ef64320dc5e6fd9f7631400cd8768a82c87e33362446ae0`

Known test vector (Twilio):

- token: `twilio-token`
- url: `https://example.com/webhooks/twilio/voice`
- params: `CallSid=CA123`, `From=+15551110000`, `To=+15552220000`
- signature: `YBtSTR1xrLSLvhJxMt1I00sUJBQ=`

Failed verification does not create a session. The HTTP body does not echo the signature.

## Not authenticated yet

SENTINEL should treat these as open on purpose for the local slice, and as blockers before any non-local deploy:

- `GET/POST /calls/...` has no operator auth.
- `WS /media/stream/{provider}` trusts a valid `call_id` or Twilio `CallSid` that already exists. It does not check a stream token.
- The fixed-tone reply and in-memory store are process-local.

Bind the process to localhost, or put an authenticating proxy in front, until that work lands.

## Logging

Structured logs include telemetry names, ids, timing, and packet counts. They do not include webhook bodies, audio payloads, or the webhook secret. `GET /calls/{id}` does return `raw_b64` to the local operator so tests can prove observation. Do not expose that route publicly.

## Carrier side effects

`forward_call` on Twilio updates the live call with `<Dial>` only when both `SWITCHBOARD_TWILIO_ACCOUNT_SID` and `SWITCHBOARD_TWILIO_AUTH_TOKEN` are set. Without them the API returns 503 and the session stays where it was. Destinations must match E.164 (`+` and 8–15 digits). Inbound `From` / `To` are stored as received because spoofed caller ids are part of the evidence, not something this slice dials.
