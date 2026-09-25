# Telephony providers

> **DRAFT (BELL bootstrap).** ATLAS can fold this into the architecture set. Operators use it to run the mock simulator or point Twilio at the webhooks.

## Mock provider (no carrier account)

Environment:

```bash
SWITCHBOARD_PUBLIC_BASE_URL=http://127.0.0.1:8000
SWITCHBOARD_MEDIA_WS_BASE_URL=ws://127.0.0.1:8000
SWITCHBOARD_MOCK_WEBHOOK_SECRET=dev-mock-secret
```

Start the API (`uvicorn` or `docker compose up --build`), then:

```bash
python -m switchboard.simulator --base-url http://127.0.0.1:8000 --secret dev-mock-secret
```

The simulator signs `POST /webhooks/mock/voice`, opens the `media_stream_url` from the JSON answer, sends one μ-law payload, and sends `hangup`. Stdout is a JSON result. Exit code 0 means the domain events and the fixed tone matched.

Webhook URL: `POST {SWITCHBOARD_PUBLIC_BASE_URL}/webhooks/mock/voice`

Status URL: `POST {SWITCHBOARD_PUBLIC_BASE_URL}/webhooks/mock/status`

Media URL: `{SWITCHBOARD_MEDIA_WS_BASE_URL}/media/stream/mock`

Signature header: `X-Switchboard-Signature: sha256=<hex>` over the raw body. See `docs/SECURITY.md` for the test vector.

## Twilio

Create a Twilio account you control and buy or verify a number you will use only as a honeypot. Do not point this service at numbers you do not operate.

Set:

```bash
SWITCHBOARD_PUBLIC_BASE_URL=https://pbx.example.com
SWITCHBOARD_MEDIA_WS_BASE_URL=wss://pbx.example.com
SWITCHBOARD_TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SWITCHBOARD_TWILIO_AUTH_TOKEN=your-auth-token
SWITCHBOARD_MOCK_WEBHOOK_SECRET=replace-the-local-default
```

`SWITCHBOARD_PUBLIC_BASE_URL` must be the exact origin Twilio will request, including `https`, with no trailing slash. The signature covers that origin plus the path.

In the Twilio console for the honeypot number:

| Twilio field | Value |
| --- | --- |
| A call comes in (webhook) | `https://pbx.example.com/webhooks/twilio/voice` (HTTP POST) |
| Call status changes | `https://pbx.example.com/webhooks/twilio/status` (HTTP POST) |

The voice webhook returns TwiML that connects a Media Stream to:

```text
wss://pbx.example.com/media/stream/twilio
```

Twilio opens that socket itself. You do not put the WebSocket URL in the console’s voice webhook field. The stream starts after `start.start.callSid` matches the `CallSid` from the voice webhook.

Local tunneling (ngrok, Cloudflare Tunnel, or similar) is required for Twilio to reach a laptop. Set both public URL env vars to that tunnel origin (`https` and `wss`) before placing a test call from a phone to the honeypot number.

Forwarding (`POST /calls/{call_id}/forward`) updates the live Twilio call with `<Dial>` via the Calls REST API. It needs both the account SID and the auth token. Hangup from the WebSocket closing is enough to finish a stream-only TwiML document; with credentials, `terminate_call` also sets the Twilio call status to `completed`.

Without `SWITCHBOARD_TWILIO_AUTH_TOKEN`, Twilio webhooks fail closed with HTTP 401.

## Swap a vendor later

Implement `TelephonyProvider`, `WebhookVerifier`, and `MediaFramer`. Register them in `switchboard.container.build_container`. Do not branch vendor logic inside `CallLifecycle` or the FastAPI routes.
