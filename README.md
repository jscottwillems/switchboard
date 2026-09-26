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

That command is LAN HTTP. It does not start the HTTPS ingress.

| URL | Process |
| --- | --- |
| http://localhost:5173 | Dashboard (browser and home-screen icon) |
| http://localhost:8000/health | API, for curl on this computer |
| http://localhost:8001/health | Media gateway |
| http://localhost:8002/health | Intelligence |

Open the dashboard in a desktop browser at `http://localhost:5173`. The page calls same-origin `/v1`. The dashboard container proxies that prefix to the API. A phone does not use `http://localhost:8000`, because on the phone that name is the phone.

### Phone on the same Wi-Fi

No TestFlight build and no native iOS app. Use Safari.

1. On the computer running compose, note a LAN address (`hostname -I` on Linux, or the Wi-Fi address in system settings).
2. Allow inbound TCP `5173` on that computer if a firewall is on.
3. On the iPhone, join the same Wi-Fi and open `http://<lan-ip>:5173` in Safari. Example: `http://192.168.1.20:5173`.
4. Share sheet → Add to Home Screen. The icon comes from the web app manifest and `apple-touch-icon`. The start URL is `/dashboard/live`.

The service worker is registered for the ops UI only. Safari installs it in a secure context (`https`, or `localhost` on the computer). A plain `http://<lan-ip>` page can still be added to the home screen; the worker registration fails there until the stack is served over HTTPS. The default compose file does not terminate TLS. Leave `docker-compose.ingress.yml` out of that command. The next section is the opt-in path that does terminate TLS, and loading that file binds port `5173` to localhost.

Read routes require `X-Switchboard-Operator-Token`. Compose defaults `SWITCHBOARD_OPERATOR_TOKEN` to `dev-operator-token` on the API and bakes the same value into the dashboard as `VITE_OPERATOR_TOKEN`. Set `SWITCHBOARD_OPERATOR_TOKEN` in `.env` to override both, then rebuild the dashboard image. The page sends that header on API-mode fetches. `VITE_OPS_DATA=mock` does not. `SWITCHBOARD_DEV_OPERATOR_BYPASS` is unset, so reads require the token even when `SWITCHBOARD_ENV=dev`. The placeholder is for this computer and a phone on the same LAN. There is no login screen. Vite inlines the token into the JavaScript bundle. Anyone who can load the dashboard can read it and call the read API. Rotating the placeholder stops the well-known value from working. It does not create per-operator login.

### HTTPS for a phone secure context

`docker-compose.ingress.yml` puts TLS in front of the dashboard origin so the phone still uses one host. The page keeps calling same-origin `/v1`. Postgres and Redis are not on that edge. The ingress file also binds the API, media gateway, intelligence, Postgres, Redis, and port `5173` to `127.0.0.1` only. Desktop curl to `http://localhost:8000` still works. Use one profile. Docker Compose v2.24 or newer is required (`!override` replaces the default port publishes). Do not set `SWITCHBOARD_CORS_ORIGINS` to `*`.

Before a tunnel URL or any other shared URL, rotate the placeholders. They are in this repository.

```sh
openssl rand -hex 32
```

Put one value in `.env` as `SWITCHBOARD_OPERATOR_TOKEN` and a second as `SWITCHBOARD_INTERNAL_TOKEN`. For `npm run dev`, set the same operator value as `VITE_OPERATOR_TOKEN` in `apps/dashboard/.env`. Then start the stack with `--build` so the dashboard image picks up the operator token. `SWITCHBOARD_DEV_OPERATOR_BYPASS` stays unset. This is still a shared secret in the bundle, not a login.

The quick tunnel is the path that does not need a VPS, a domain, or an inbound port. Cloudflare assigns an ephemeral `https://*.trycloudflare.com` name. Safari trusts that certificate, so the service worker can register. The name changes every start. Add to Home Screen again after a restart. Anyone who has the URL can open the board.

```sh
COMPOSE_PROFILES=tunnel docker compose -f docker-compose.yml -f docker-compose.ingress.yml up --build
```

The URL is in the tunnel logs:

```sh
COMPOSE_PROFILES=tunnel docker compose -f docker-compose.yml -f docker-compose.ingress.yml logs -f tunnel
```

On the iPhone, open that `https://` URL, then Share sheet → Add to Home Screen. The start URL is still `/dashboard/live`.

A named tunnel keeps one hostname. Create the tunnel in Cloudflare, set its origin to `http://edge_tunnel:80`, and put the token in `.env` as `CLOUDFLARE_TUNNEL_TOKEN`. Do not commit the token.

```sh
COMPOSE_PROFILES=tunnel-named docker compose -f docker-compose.yml -f docker-compose.ingress.yml up --build
```

Same-Wi-Fi HTTPS without Cloudflare uses Caddy's internal CA. Set `SWITCHBOARD_PUBLIC_HOST` to the computer's LAN IP, with no scheme and no port. Allow inbound TCP `80` and `443`.

```sh
SWITCHBOARD_PUBLIC_HOST=192.168.1.20 COMPOSE_PROFILES=https docker compose -f docker-compose.yml -f docker-compose.ingress.yml up --build
```

Send the local root to the phone and open it. Settings → Profile Downloaded → Install, then Settings → General → About → Certificate Trust Settings → enable full trust for that root. Open `https://192.168.1.20` (the same host you set). An untrusted certificate is not a secure context, and the service worker will not install.

```sh
COMPOSE_PROFILES=https docker compose -f docker-compose.yml -f docker-compose.ingress.yml exec edge cat /data/caddy/pki/authorities/local/root.crt > switchboard-local-root.crt
```

If the phone already trusts an mkcert root, replace `tls internal` in `deploy/ingress/Caddyfile.lan` with `tls /certs/cert.pem /certs/key.pem` and mount those files into the `edge` service at `/certs`. Do not commit the key.

A public DNS name and open ports `80` and `443` can use automatic HTTPS. Point the name at this computer first. Set `SWITCHBOARD_ACME_EMAIL` to a real mailbox.

```sh
SWITCHBOARD_PUBLIC_HOST=board.example.com SWITCHBOARD_ACME_EMAIL=ops@example.com COMPOSE_PROFILES=https-public docker compose -f docker-compose.yml -f docker-compose.ingress.yml up --build
```

The phone opens `https://board.example.com`. No VPS is required when the hostname reaches this machine, either through the tunnel or through ports `80` and `443`.

What the edge serves:

| Path | Ingress |
| --- | --- |
| Dashboard and `/v1/calls`, `/v1/campaigns` | Proxied to the dashboard origin |
| `/v1/internal`, `/v1/telephony`, `/v1/streams` | `404`. Not exposed |
| Postgres, Redis, port `8000`, port `8001`, port `8002` | Not on the edge. Loopback only while this file is in use |

`MEDIA_GATEWAY_PUBLIC_WS` stays `ws://localhost:8001/v1/streams` until carrier media is on this edge. When you enable it, delete the `/v1/streams` deny in `deploy/ingress/routes.caddy`, proxy that path to `media_gateway:8001`, and set `MEDIA_GATEWAY_PUBLIC_WS=wss://<public-host>/v1/streams`. Do not publish `ws://` on a public host. Carrier webhooks are the same kind of later edit: proxy `/v1/telephony` to `api:8000` only after `SWITCHBOARD_DEV_WEBHOOK_BYPASS` is unset and `SWITCHBOARD_ENV` is not `dev`. Leave `/v1/internal` off the edge. The commented blocks in `deploy/ingress/routes.caddy` are that later edit. They are not active.

The compose file sets `SWITCHBOARD_DEV_WEBHOOK_BYPASS=1` for local development only. A signed mock webhook:

```sh
sh scripts/mock_inbound_call.sh
```

The API returns a `connect_stream` instruction and stores the session when `to_e164` is an active operator number. `GET /v1/calls` and `GET /v1/calls/{id}` return those stored rows. The live board lists sessions whose `state` is `in_progress`. A new mock call stays `ringing` until a signed `POST /v1/telephony/status/mock` with `"status": "in_progress"`. `GET /v1/campaigns` and `GET /v1/campaigns/{id}` return stored campaigns. The dashboard campaign, system, and report screens stay on mock fixtures.

## Dashboard

The operator UI is `apps/dashboard`. Live, call history, and call detail read `GET /v1/calls` and `GET /v1/calls/{id}`. Campaigns, system, and reports stay on mock fixtures. Set `VITE_OPS_DATA=mock` to keep every screen on fixtures when the API is down.

```sh
cd apps/dashboard
npm install
npm run dev
```

`npm run dev` proxies `/v1` to `http://127.0.0.1:8000` when `VITE_API_BASE_URL` is unset. `npm run preview` does the same for a production build on port 4173. Leave the base unset for same-origin requests. Set `VITE_API_BASE_URL` only to call another origin, and add that origin to `SWITCHBOARD_CORS_ORIGINS`. The live board polls every 5 seconds (`VITE_LIVE_POLL_MS`).

Open `http://localhost:5173` for the Vite dev server, or the compose URL above for the nginx image. Routes: `/dashboard/live`, `/dashboard/calls`, `/dashboard/calls/:id`, `/dashboard/campaigns`, `/dashboard/campaigns/:id`, `/dashboard/system`, `/dashboard/reports`, `/dashboard/reports/:reportId`.

`npm run typecheck` and `npm run build` run in that directory. Shapes the screens need, and the fields the read API does not return yet, are listed in [docs/FRONTEND_DATA_REQUIREMENTS.md](docs/FRONTEND_DATA_REQUIREMENTS.md).

Without Docker, install and test the contracts:

```sh
make install-dev
make test
make test-mvp-smoke
```

`make test-mvp-smoke` is the mock vertical slice: signed voice webhook, fixture audio, speak-back, `callback_number` finding, a signed status callback to `in_progress`, and `GET /v1/calls` plus `GET /v1/calls/{id}`. It needs the same Postgres and Redis as `make test`.

Python 3.12 and Node 22 are the local baselines. Copy `.env.example` to `.env` for host processes. Those values are development defaults.
