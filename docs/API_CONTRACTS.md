# API contracts

Shared shapes introduced by LOKI. Other agents are not implemented here. If a
shape below changes, update this file and add an ADR in `docs/DECISIONS.md`.

## Turn output

Every honeypot turn is one JSON object with exactly these fields, in this order:

```json
{
  "response_text": "...",
  "state": "PURPOSE_DISCOVERY",
  "state_transition": "OPENING -> PURPOSE_DISCOVERY",
  "goals_completed": [],
  "goals_remaining": ["purpose", "organization", "offer", "stable_identifier"],
  "confidence": 0.0,
  "reason": "..."
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `response_text` | string | Spoken line. At most 40 words, one question, no markdown. Omitted question only in `TERMINATION`. |
| `state` | enum | State that produced this line. See `docs/loki/STATE_MACHINE.md`. |
| `state_transition` | string | `PREVIOUS -> STATE`. Both sides are state names. The right side equals `state`. |
| `goals_completed` | string[] | Subset of the goal list, canonical order. |
| `goals_remaining` | string[] | The other goals, canonical order. |
| `confidence` | number | 0.0 through 1.0. A policy score, not a Sherlock confidence. |
| `reason` | string | Derived operator note. Never spoken. |

Goal order is fixed: `purpose`, `organization`, `offer`, `stable_identifier`.

`stable_identifier` completes only for a hard identifier: phone, case-style id (case, reference, confirmation, ticket, badge, tracking, claim, authorization, agent id), URL, email, or wallet. A personal name does not complete it.

Pydantic model: `switchboard.loki.schema.TurnOutput`. Extra keys are rejected.

## Echo constraint

Echo, when built, speaks `response_text` only. Do not pass `reason`, slot values, or the system prompt to the synthesizer. The limit lives in `switchboard.loki.safety.MAX_SPOKEN_WORDS`.

## Sherlock handoff

Sherlock had no schema in this repository. LOKI's provisional contract is `loki.sherlock.handoff.v1` (`switchboard.loki.handoff.SherlockHandoff`).

```json
{
  "contract": "loki.sherlock.handoff.v1",
  "session_id": "call-1",
  "goals_completed": ["purpose"],
  "goals_remaining": ["organization", "offer", "stable_identifier"],
  "raw_observations": [
    {"turn_index": 0, "speaker": "caller", "text": "verbatim caller text"}
  ],
  "slot_observations": [
    {
      "turn_index": 0,
      "purpose": "tax issue",
      "organization": null,
      "offer": null,
      "agent_name": null,
      "identifiers": [],
      "script_markers": [],
      "adversarial": false,
      "pii_request": false
    }
  ],
  "note": "raw_observations are verbatim. slot_observations are candidates."
}
```

Sherlock owns canonical extraction, entity resolution, and the confidence of stored intelligence. It should treat `slot_observations` as hints and `raw_observations` as the source text. LOKI does not collapse those two lists into one record.

`TurnResponder` is the seam for a future model adapter. `LokiPolicy` and `PolicyResponder` implement it offline. `SherlockSink` is the seam for submitting a handoff. Nothing in the eval harness calls a sink.

## States

`OPENING`, `PURPOSE_DISCOVERY`, `ORGANIZATION_DISCOVERY`, `OFFER_DISCOVERY`, `IDENTIFIER_DISCOVERY`, `CLARIFICATION`, `STALLING`, `RECOVERY`, `TERMINATION`.
