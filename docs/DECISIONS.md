# Decisions

Accepted for contract 0.1.0 on 2026-09-25. Superseding an ADR means a new ADR that names the old one, plus the schema and doc updates that ADR requires.

## ADR-001 — Monorepo of apps and packages

**Context.** Nine agents share one vertical slice. Telephony, speech, dialogue, extraction, and the dashboard change at different speeds.

**Decision.** One repository. Deployable processes live in `apps/`. Shared ports and contracts live in `packages/`. Apps may depend on packages. Packages do not depend on apps.

**Consequences.** Agents can ship a package without redeploying every app, and the import graph stays acyclic. A contract change is still a coordinated pull request because the docs and `packages/schemas` move together.

## ADR-002 — Three record layers

**Context.** A honeypot produces hostile, spoofed, and model-generated text. Mixing "the caller said this" with "we think this is a campaign" makes later review untrustworthy.

**Decision.** Observations (`obs`), interpretations (`interp`), and campaign attribution (`attr`) are separate Postgres schemas and separate Pydantic types with `record_layer`. Findings cite transcript ids. Attributions cite finding ids. Observations do not carry campaign or confidence columns. `stt_confidence` stays on the transcript and is not reused as Switchboard confidence.

**Consequences.** Queries for the dashboard join explicitly. A bug that writes a campaign id onto a transcript has nowhere to land. Reports can show the chain. More tables are required up front.

## ADR-003 — Pydantic is canonical, TypeScript is a mirror

**Context.** The API is Python and the dashboard is Vue. Generating TypeScript is not in the skeleton.

**Decision.** `packages/schemas/switchboard_schemas` is the machine-readable contract. `packages/schemas/ts/index.ts` is a hand-written mirror. Agents change Python first and update the mirror in the same pull request. A test checks that every `EventType` string appears in the TypeScript file.

**Consequences.** Drift is possible between releases of the mirror. The test catches missing event names, not missing fields. A later ATLAS ticket can replace the mirror with codegen. Until then, reviewers diff both files.

## ADR-004 — Hot path in-process, durable path on the bus

**Context.** Reply audio has a latency budget. Extraction and campaign clustering do not.

**Decision.** `media_gateway` calls `SttPort`, `ResponseSelector`, and `TtsPort` in-process. Everything that other apps need is an `EventEnvelope` on Redis. The gateway does not call intelligence over HTTP during a turn.

**Consequences.** LOKI's selector is a library, not a service, in the MVP. A slow extractor cannot stall audio. Selector bugs are deployed with the gateway.

## ADR-005 — Audio frames stay off the bus

**Context.** Frame-level audio would dominate Redis, show up in logs, and blur the line between raw media and derived text.

**Decision.** Switchboard Media Protocol frames exist only on the media WebSocket. The bus carries transcripts, decisions, and lifecycle events. The MVP does not retain audio bytes.

**Consequences.** ECHO cannot replay audio from Redis. CLERK's later evidence bundles cite transcript observations unless a future ADR allows encrypted audio objects outside the bus.

## ADR-006 — One writer per table group

**Context.** Two writers for `obs.call_session` will race.

**Decision.** API projector writes `obs.*` and `interp.conversation_turn`. The extractor writes `interp.intelligence_finding`. The correlator writes `attr.*`. The gateway writes no SQL. The dashboard writes nothing.

**Consequences.** The gateway must publish events for anything that should be stored, including its own stream lifecycle. Cross-process reads go through the API.

## ADR-007 — Postgres is the record, Redis is the bus and the token cache

**Context.** The slice needs a durable call record and a fan-out mechanism.

**Decision.** Postgres holds the layers in ADR-002. Redis holds `switchboard.events` and stream tokens. Losing Redis loses unpublished or unconsumed events and outstanding tokens. It does not lose committed rows.

**Consequences.** Token validation is an API responsibility backed by Redis, not a Postgres lookup, so the gateway is not waiting on SQL to accept a socket. Operators do not treat the stream as an archive.

## ADR-008 — Carrier specifics stop at the telephony package

**Context.** The first milestone needs a callable webhook without a real carrier account.

**Decision.** `CarrierProvider` in 0.1.0 is `mock`. `MockVoiceWebhook` and `MockStatusWebhook` are Switchboard models. A future provider is a parser and a signature verifier inside `packages/telephony` that emits the same internal events. Provider JSON is stored on `obs.webhook_receipt.payload` and does not become the domain model.

**Consequences.** BELL can add a carrier without changing intelligence or the dashboard. The mock signature header is a development stand-in, not a security control. See ADR-012 and `docs/SECURITY.md`.

## ADR-009 — Failure isolation of the live call

**Context.** The product is a honeypot. Dropping the caller because the dashboard or the extractor is down defeats the recording goal.

**Decision.** The media socket keeps running when intelligence, the dashboard, or a single selector call fails. A selector failure yields no audio for that turn. New calls fail closed when the webhook signature, number enrollment, or token issue cannot be completed.

**Consequences.** Operators may see a call in the dashboard later than it started. They will not see a finding for a turn whose event was lost (ADR-011) until a replay exists.

## ADR-010 — One intelligence process, two modules

**Context.** SHERLOCK and WATSON have different owners and different failure modes, and the MVP does not need two deployments.

**Decision.** `apps/intelligence` hosts the extractor and the correlator as separate modules and separate Redis consumer groups. They do not share a write table. Splitting them into processes later does not change the event names.

**Consequences.** A bad correlator deploy currently ships beside the extractor. Owners stay inside their modules. WATSON does not edit extractor rules to "help" attribution.

## ADR-011 — No transactional outbox in the MVP

**Context.** An outbox would couple webhook transactions to the bus and is more machinery than the skeleton should hide.

**Decision.** 0.1.0 publishes after the in-memory or database work, without an outbox. A crash can drop an event. Consumers are idempotent. A future ADR can add an outbox in `apps/api` if lost call rows show up in testing.

**Consequences.** The first milestone can lose a transcript projection. It must not invent a transcript to fill the gap.

## ADR-012 — The honeypot is not an outbound agent

**Context.** Callers are hostile. Content they dictate may name phone numbers, URLs, or payment steps.

**Decision.** The MVP places no outbound calls, fetches no caller-supplied URL, and executes no tool because a caller asked. Extracted URLs and numbers are stored as findings. They are not dialed or requested.

**Consequences.** Engagement is limited to audio toward the caller who is already on an enrolled number. CLERK and RADAR display strings. They do not turn them into actions.

## ADR-013 — Version the HTTP prefix and the event envelope

**Context.** Agents will add fields during the milestone.

**Decision.** HTTP routes live under `/v1`. Events carry `event_version: 1`. Adding an optional field is allowed when Pydantic's extra-forbid models and the TypeScript mirror update together. Renaming or removing a field requires a new version.

**Consequences.** Old and new producers are distinguishable on the stream. The dashboard targets `/v1` only.
