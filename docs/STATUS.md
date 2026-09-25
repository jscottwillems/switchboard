# Status

LOKI's first slice is in `switchboard.loki`. The repository had no `CallSession`, no Sherlock schema, and no other agent packages when this work started. Telephony is intentionally out of this change. The offline eval is the check that the conversation policy behaves as specified.

## HANDOFF — LOKI — 2026-09-25T20:40:20Z

Completed:
- Conversation state machine for OPENING, PURPOSE_DISCOVERY, ORGANIZATION_DISCOVERY, OFFER_DISCOVERY, IDENTIFIER_DISCOVERY, CLARIFICATION, STALLING, RECOVERY, and TERMINATION.
- System prompt for the honeypot speaker, including refusal rules and the spoken-text limit.
- Canonical seven-field turn schema (`TurnOutput`) with goal order enforced.
- 20 synthetic scam-call scenarios and their expected trajectories.
- Offline eval harness (`python -m switchboard.loki.eval` and `pytest`) with no live telephone path and no model API.
- Provisional Sherlock handoff and a `loki.turn.completed` event, documented because those agents are not in the repo.

Files changed:
- README.md
- pyproject.toml
- .gitignore
- docs/ARCHITECTURE.md
- docs/API_CONTRACTS.md
- docs/DATA_MODEL.md
- docs/DECISIONS.md
- docs/EVENTS.md
- docs/STATUS.md
- docs/loki/STATE_MACHINE.md
- switchboard/__init__.py
- switchboard/loki/__init__.py
- switchboard/loki/states.py
- switchboard/loki/goals.py
- switchboard/loki/schema.py
- switchboard/loki/safety.py
- switchboard/loki/observe.py
- switchboard/loki/policy.py
- switchboard/loki/handoff.py
- switchboard/loki/prompt.py
- switchboard/loki/prompts/system_prompt.md
- switchboard/loki/data/scenarios.json
- switchboard/loki/eval/__init__.py
- switchboard/loki/eval/__main__.py
- switchboard/loki/eval/harness.py
- tests/loki/test_observe.py
- tests/loki/test_policy.py
- tests/loki/test_schema.py
- tests/loki/test_handoff.py
- tests/loki/test_prompt_contract.py
- tests/loki/test_harness.py

Interfaces added/changed:
- Turn JSON: `response_text`, `state`, `state_transition`, `goals_completed`, `goals_remaining`, `confidence`, `reason`.
- Goals, in order: `purpose`, `organization`, `offer`, `stable_identifier`. Hard identifiers complete the last goal. A personal name does not.
- `loki.sherlock.handoff.v1` (`SherlockHandoff`): verbatim caller turns plus candidate slots. Sherlock still owns canonical extraction.
- Event `loki.turn.completed`: raw caller utterance plus the derived turn.
- `TurnResponder` and `SherlockSink` protocols. `LokiPolicy` / `PolicyResponder` are the offline implementations. No sink is called.
- Spoken constraint for Echo: `response_text` only, at most 40 words, one question except in TERMINATION.

Tests:
- `pytest`: 27 passed.
- `python -m switchboard.loki.eval`: prompt contract PASS, 20/20 scenarios passed, all nine states covered. No network and no telephone.

Dependencies:
- Runtime: pydantic >= 2.
- Tests: pytest >= 8.
- Python >= 3.11.

Blocking issues:
- No telephony `CallSession` and no audio path, so this slice cannot join a live call.
- Sherlock's extraction schema is absent. The handoff is provisional until Sherlock defines canonical entities.
- The eval does not call a model. A live `TurnResponder` is not implemented.
- Echo, Watson, and Sentinel have no packages here. Their needs are documented as contracts only.

Recommended next work:
- Sherlock: consume `loki.sherlock.handoff.v1`, keep raw text and LOKI slots distinct, and publish the canonical extraction schema.
- Echo: speak `response_text` only and honor the 40-word limit.
- Watson: cluster on the hard identifiers and `script_markers` the policy is trying to elicit.
- Sentinel: red-team the system prompt with a real model. The offline policy already refuses disclosure, and that is not a substitute for a model jailbreak run.
- Orchestrator: feed caller transcripts into `LokiPolicy.step` and publish `loki.turn.completed`.
