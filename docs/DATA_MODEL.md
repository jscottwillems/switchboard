# Data model

There is no telephony `CallSession` in this repository. The models below are the conversation slice LOKI needs. A future call record can point at `session_id` without folding these fields into a transcript blob.

## Raw and derived stay apart

| Record | Kind | Contents | Must not contain |
| --- | --- | --- | --- |
| `RawCallerUtterance` | observation | `turn_index`, `speaker` (`caller`), verbatim `text` | state, goals, confidence, extracted slots |
| `SlotObservation` | derived candidate | purpose label, organization string, offer label, agent name, identifier hits, script phrases, probe flags | a claim that Sherlock has confirmed them |
| `TurnOutput` | derived decision | spoken line, state, transition, goals, confidence, reason | the raw utterance copied into `response_text` |

`reason` explains the decision for an operator. It is derived. It is not a second copy of the caller audio and it is not speech.

Identifier hits store the matched text (`phone`, `case_id`, `url`, `email`, `wallet`) so Watson can later correlate callbacks and scripted ids. Those hits are still candidates. `case_id` covers case, reference, confirmation, ticket, badge, tracking, claim, authorization, and agent-id numbers. The original sentence remains on the raw utterance.

## Session

`ConversationSession` holds:

- `session_id`
- current `state` (starts at `OPENING`)
- `goals_completed`
- clarification, recovery, and stall counters
- `raw_observations`
- `slot_observations`
- `turns` (derived `TurnOutput` list)

Counters are control state for the policy. They are not intelligence.

## Goals

Completing a goal means "the caller has supplied enough for LOKI to stop asking that question." It does not mean the claim is true. A caller can name a fake bank and still complete `organization`.
