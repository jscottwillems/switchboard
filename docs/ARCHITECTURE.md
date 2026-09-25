# Architecture

Project Switchboard is a scam-call honeypot. This repository started with no
code, no `CallSession` model, and no Sherlock extraction schema. The first
slice is LOKI only: what the honeypot says, which goal it is pursuing, and how
that behavior is evaluated without a phone line.

## What exists

`switchboard.loki` is a library. It does not open sockets, place calls, or call
a model API.

| Piece | Role |
| --- | --- |
| `switchboard/loki/states.py` | Nine conversation states |
| `switchboard/loki/goals.py` | Four explicit goals, in a fixed order |
| `switchboard/loki/observe.py` | Shallow, deterministic reading of one caller turn |
| `switchboard/loki/policy.py` | Reference state machine and spoken lines |
| `switchboard/loki/prompts/system_prompt.md` | Same contract, written for a future model |
| `switchboard/loki/schema.py` | Canonical turn JSON |
| `switchboard/loki/handoff.py` | Provisional payloads for agents that are not in this repo |
| `switchboard/loki/eval/` | Offline scenario replay |

## What this slice does not build

- Telephony, audio, or a `CallSession` owner. A later session can store LOKI's `session_id` and turn events.
- Sherlock's canonical intelligence store. LOKI emits candidate slots only.
- Echo's speech pipeline. Echo, when it exists, should speak `response_text` and nothing else from the turn.
- Watson's campaign clustering. The policy prefers callbacks, case ids, URLs, emails, wallets, and repeated script phrases so Watson has stable features later.
- Sentinel's red-team runner. The prompt and the policy both refuse disclosure; they are not a full adversarial lab.

## Turn path

1. A caller utterance arrives as text. That string is a raw observation.
2. `observe` produces a derived reading: purpose, organization, offer, hard identifiers, probes, and goodbye.
3. `LokiPolicy.step` updates goals, chooses the next state, and returns one `TurnOutput`.
4. `build_turn_event` wraps the raw utterance and the derived turn.
5. `build_sherlock_handoff` packages the session for Sherlock when an orchestrator exists.

`reason` is an operator note. It must not be spoken. `response_text` is the only field meant for text-to-speech.
