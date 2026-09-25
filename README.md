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

The API returns a `connect_stream` instruction and stores the session when `to_e164` is an active operator number. The dashboard shows an empty call list until the read-model tickets land.

Without Docker, install and test the contracts:

```sh
make install-dev
make test
```

Python 3.12 and Node 22 are the local baselines. Copy `.env.example` to `.env` for host processes. Those values are development defaults.
