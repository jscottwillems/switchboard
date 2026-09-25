# Decisions

## ADR-001 — LOKI is a library package

The repository had no service layout, no `CallSession`, and no agent packages. LOKI lives at `switchboard.loki` so the state machine and the eval harness import and run under `pytest` with no network. A process, a phone gateway, and other agents can depend on this package later. They are not stubbed in as empty services.

## ADR-002 — The offline reference is a deterministic policy

The system prompt in `switchboard/loki/prompts/system_prompt.md` is the contract a model should follow. The eval harness does not call a model and does not open a telephone connection. `LokiPolicy` is the inspectable reference that executes the same states, goals, and refusal rules. A later `TurnResponder` may call a model, and it must still return `TurnOutput`. Replacing the reference with a live model is a separate change.

## ADR-003 — Provisional Sherlock handoff

Sherlock's extraction schema is not in this repository. LOKI does not invent Sherlock's canonical entities. It publishes `loki.sherlock.handoff.v1`: verbatim caller turns plus candidate slots and the four conversation goals. Sherlock may ignore the candidates and re-read the raw text. Until Sherlock lands a schema, this handoff is the interface LOKI expects.

Hard identifiers complete `stable_identifier`. A personal name is stored as `agent_name` and does not complete that goal, because Watson needs callbacks, case ids, URLs, emails, and wallets more than a first name.

## ADR-004 — Seven-field turn JSON

The turn object has exactly `response_text`, `state`, `state_transition`, `goals_completed`, `goals_remaining`, `confidence`, and `reason`. Extra keys are invalid. Spoken audio uses `response_text` only, capped at 40 words, so Echo can keep latency down without a second prose field. Operator explanation stays in `reason`.

## ADR-005 — Raw utterances are not interpretations

`RawCallerUtterance` stores caller text unchanged. Derived labels live on `SlotObservation` and `TurnOutput`. Mixing them would make it impossible to tell what the caller said from what LOKI inferred. See `docs/DATA_MODEL.md`.
