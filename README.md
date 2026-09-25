# Switchboard

Operator-controlled scam-call honeypot. This repository currently contains the first telephony vertical slice (BELL): an inbound call webhook becomes a `CallSession`, a media WebSocket observes one audio packet, a known tone is returned, and hangup emits `call.completed`.

Numbers placed on this system are expected to be controlled by the operator. The slice does not include a dashboard, speech-to-text, text-to-speech, or campaign correlation.

## Run locally

Python 3.12 is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn switchboard.main:app --reload --host 127.0.0.1 --port 8000
```

In another shell, drive a fake inbound call. No carrier account is required:

```bash
python -m switchboard.simulator --base-url http://127.0.0.1:8000
```

The process exits 0 when the event sequence is `call.received`, `call.connected`, `call.media.started`, `call.media.ended`, `call.completed` and the media reply matches the fixed μ-law tone.

Docker Compose runs the same API. Session state is in memory (see `docs/DECISIONS.md` ADR-001), so Redis and Postgres are not started.

```bash
docker compose up --build
python -m switchboard.simulator --base-url http://127.0.0.1:8000
```

Tests:

```bash
pytest
```

## Point a real provider at it

Twilio is the first concrete provider behind `TelephonyProvider`. Setup (env vars, voice webhook, status callback, media stream URL) is in `docs/TELEPHONY.md`.

Use the mock provider for local work. Business logic does not import Twilio; swapping vendors means adding an adapter, a verifier, and a media framer.

## Draft contracts

`docs/ARCHITECTURE.md`, `docs/API_CONTRACTS.md`, `docs/EVENTS.md`, `docs/DATA_MODEL.md`, `docs/SECURITY.md`, `docs/DECISIONS.md`, and `docs/STATUS.md` are bootstrap drafts for ATLAS to refine. Sample payloads live in `docs/fixtures/`.

## Layout

```text
switchboard/          FastAPI app, providers, media gateway, simulator
tests/                pytest coverage of the simulator path and Twilio adapter
docs/                 Draft contracts and provider setup
```
