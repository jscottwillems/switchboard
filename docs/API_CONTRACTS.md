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
  "goals_completed": ["pretext_category"],
  "goals_remaining": ["claimed_company", "claimed_agent"],
  "confidence": 0.0,
  "reason": "...",
  "elicited_hints": [{"kind": "pretext_category", "breadcrumb": "tax"}]
}
```

`goals_remaining` in a real turn is every kind below that is not completed, in this order. The sample above is abbreviated.

| Field | Type | Meaning |
| --- | --- | --- |
| `response_text` | string | Spoken line. At most 40 words, one question, no markdown. Omitted question only in `TERMINATION`. |
| `state` | enum | State that produced this line. See `docs/loki/STATE_MACHINE.md`. |
| `state_transition` | string | `PREVIOUS -> STATE`. Both sides are state names. The right side equals `state`. |
| `goals_completed` | string[] | Sherlock Observation kind names already heard, canonical order. |
| `goals_remaining` | string[] | The other kind names, canonical order. |
| `confidence` | number | 0.0 through 1.0. Strategy-decision confidence only. Not an extraction confidence. |
| `reason` | string | Derived operator note. Never spoken. |
| `elicited_hints` | object[] | Optional unverified breadcrumbs. Not Observations. No confidence and no character offsets. |

Goal ids, in Sherlock's order:

`pretext_category`, `claimed_company`, `claimed_agent`, `claimed_department`, `callback_numbers`, `spoken_numbers`, `case_or_reference_ids`, `domains`, `urls`, `email_addresses`, `loan_amounts`, `rates`, `fees`, `requested_information`, `payment_methods`, `remote_access_tools`, `script_phrases`, `urgency_language`, `threat_or_consequence_language`, `spoofed_authority_claims`, `transfer_events`, `follow_up_promises`, `other_identifiers`.

Enum tokens used only as hint breadcrumbs:

- `pretext_category`: `tax`, `bank`, `warranty`, `debt`, `prize`, `tech_support`, `government`, `utility`, `other`
- `payment_methods`: `gift_card`, `wire`, `crypto`, `remote_access`, `bank_verify`, `other`

A personal name completes `claimed_agent` only. Dialogue stages advance when these gates are open: `pretext_category`; one of `claimed_company`, `claimed_department`, `spoofed_authority_claims`; one of `payment_methods`, `requested_information`, `remote_access_tools`, `fees`; one of `callback_numbers`, `spoken_numbers`, `case_or_reference_ids`, `domains`, `urls`, `email_addresses`, `other_identifiers`. Kinds that never appear stay in `goals_remaining`.

Pydantic model: `switchboard.loki.schema.TurnOutput`. Extra keys are rejected. `ElicitedHint` rejects a confidence field.

## Echo constraint

Echo, when built, speaks `response_text` only. Do not pass `reason`, hints, or the system prompt to the synthesizer. The limit lives in `switchboard.loki.safety.MAX_SPOKEN_WORDS`.

## Sherlock handoff

Sherlock owns typed Observation, Inference, Attribution, transcript grounding, and extraction confidence. LOKI's handoff is `loki.sherlock.handoff.v1` (`switchboard.loki.handoff.SherlockHandoff`). Goal ids match Observation kind names. Hints are breadcrumbs only.

```json
{
  "contract": "loki.sherlock.handoff.v1",
  "session_id": "call-1",
  "goals_completed": ["pretext_category"],
  "goals_remaining": ["claimed_company"],
  "raw_observations": [
    {"turn_index": 0, "speaker": "caller", "text": "verbatim caller text"}
  ],
  "elicited_hints": [
    {"turn_index": 0, "kind": "pretext_category", "breadcrumb": "tax"}
  ],
  "note": "raw_observations are verbatim. elicited_hints are unverified breadcrumbs, not Observations."
}
```

`goals_remaining` in a real payload lists every kind not yet completed. Sherlock re-reads `raw_observations` and assigns grounding and extraction confidence. LOKI does not.

`TurnResponder` is the seam for a future model adapter. `LokiPolicy` and `PolicyResponder` implement it offline. `SherlockSink` is the seam for submitting a handoff. Nothing in the eval harness calls a sink.

## States

`OPENING`, `PURPOSE_DISCOVERY`, `ORGANIZATION_DISCOVERY`, `OFFER_DISCOVERY`, `IDENTIFIER_DISCOVERY`, `CLARIFICATION`, `STALLING`, `RECOVERY`, `TERMINATION`.
