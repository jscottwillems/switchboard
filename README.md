# Switchboard

Operator-controlled honeypot for scam calls: record the call, interpret it, then attribute campaigns. Those three layers stay separate.

This repository is the architecture skeleton for that system. Specialist telephony, speech, dialogue, extraction, correlation, security hardening, dashboard polish, and evidence packaging are stubs with named owners.

## Orient

Read these in order:

1. [docs/STATUS.md](docs/STATUS.md) — milestone, ownership, tickets, latest handoff
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, MVP flow, local topology
3. [docs/API_CONTRACTS.md](docs/API_CONTRACTS.md) — HTTP and WebSocket boundaries
4. [docs/EVENTS.md](docs/EVENTS.md) — bus taxonomy
5. [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — observations, interpretations, attribution
6. [docs/DECISIONS.md](docs/DECISIONS.md) — ADRs
7. [docs/SECURITY.md](docs/SECURITY.md) — baseline that later hardening has to keep

Machine-readable fields live in `packages/schemas` (Pydantic). `packages/schemas/ts` mirrors them for the dashboard. Change both together.

## Layout

| Path | What it is |
| --- | --- |
| `apps/api` | Webhooks, sessions, read API |
| `apps/media_gateway` | Media WebSocket and the audio hot path |
| `apps/intelligence` | Async extraction and correlation |
| `apps/dashboard` | Vue operator UI |
| `packages/schemas` | Canonical contracts |
| `packages/telephony` | Carrier ports |
| `packages/conversation` | Reply-selector port |
| `packages/classification` | Extractor and correlator ports |
| `packages/observability` | Log redaction helper |
| `packages/events` | Redis stream `switchboard.events` |
| `packages/repositories` | Postgres ports for `ops`, `obs`, `interp`, and `attr` |
| `sentinel/` | Resource limits and adversarial fixtures. Webhook verification stays in `packages/telephony` |

## Collaborate

- Take a ticket in `docs/STATUS.md` whose owner is you. Start immediately when the concurrent flag is yes.
- Stay inside your owned paths. Contract changes include `packages/schemas` and the matching doc in the same change.
- Do not write interpretation fields onto observation rows. Cite ids instead.
- Do not log audio, webhook bodies, or tokens. Use `switchboard_observability.log_info`.
- Append a `HANDOFF` section to `docs/STATUS.md` when you finish a turn: completed work, files, interfaces, tests, dependencies, blockers, and the next recommendation.

## Local skeleton

```sh
docker compose up --build
```

| URL | Process |
| --- | --- |
| http://localhost:5173 | Dashboard |
| http://localhost:8000/health | API |
| http://localhost:8001/health | Media gateway |
| http://localhost:8002/health | Intelligence |

The compose file sets `SWITCHBOARD_DEV_WEBHOOK_BYPASS=1` for local development only. A signed mock webhook:

```sh
sh scripts/mock_inbound_call.sh
```

The API returns a `connect_stream` instruction and stores the session when `to_e164` is an active operator number. `GET /v1/calls` and `GET /v1/calls/{id}` return those stored rows. Campaign routes still return an empty list or `404`.

## Dashboard

The operator UI is `apps/dashboard`. Live, call history, and call detail read `GET /v1/calls` and `GET /v1/calls/{id}`. Campaigns, system, and reports stay on mock fixtures. Set `VITE_OPS_DATA=mock` to keep every screen on fixtures when the API is down.

```sh
cd apps/dashboard
npm install
npm run dev
```

`npm run dev` proxies `/v1` to `http://127.0.0.1:8000` when `VITE_API_BASE_URL` is unset. Set `VITE_API_BASE_URL=http://localhost:8000` to call the API directly. The production build defaults that base to `http://localhost:8000`. The live board polls every 5 seconds (`VITE_LIVE_POLL_MS`).

Open `http://localhost:5173`. Routes: `/dashboard/live`, `/dashboard/calls`, `/dashboard/calls/:id`, `/dashboard/campaigns`, `/dashboard/campaigns/:id`, `/dashboard/system`, `/dashboard/reports`, `/dashboard/reports/:reportId`.

`npm run typecheck` and `npm run build` run in that directory. Shapes the screens need, and the fields the read API does not return yet, are listed in [docs/FRONTEND_DATA_REQUIREMENTS.md](docs/FRONTEND_DATA_REQUIREMENTS.md).

Without Docker, install and test the contracts:

```sh
make install-dev
make test
make test-mvp-smoke
```

`make test-mvp-smoke` is the mock vertical slice: signed voice webhook, fixture audio, speak-back, `callback_number` finding, and `GET /v1/calls` plus `GET /v1/calls/{id}`. It needs the same Postgres and Redis as `make test`.

Python 3.12 and Node 22 are the local baselines. Copy `.env.example` to `.env` for host processes. Those values are development defaults.
