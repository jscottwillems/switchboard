# Data model

There is no telephony `CallSession` in this repository. The models below are the conversation slice LOKI needs. A future call record can point at `session_id` without folding these fields into a transcript blob.

## Raw text, breadcrumbs, and strategy stay apart

| Record | Kind | Contents | Must not contain |
| --- | --- | --- | --- |
| `RawCallerUtterance` | raw caller text | `turn_index`, `speaker` (`caller`), verbatim `text` | state, goals, confidence, hints |
| `ElicitedHint` / `RecordedHint` | unverified breadcrumb | kind name plus a short note, and a turn index on the session copy | extraction confidence, character offsets, an Observation, Inference, or Attribution |
| `TurnOutput` | strategy decision | spoken line, state, transition, goal ids, strategy confidence, reason, hints for that turn | the raw utterance copied into `response_text` |

Sherlock owns typed Observations. LOKI's goal ids are those kind names, which means "this kind has come up," not "Sherlock has confirmed it."

`reason` explains the strategy decision for an operator. It is not speech and it is not a second copy of the caller audio.

`TurnOutput.confidence` is strategy-decision confidence only. It is not the confidence of an extraction.

## Session

`ConversationSession` holds:

- `session_id`
- current `state` (starts at `OPENING`)
- `goals_completed` (Sherlock kind names)
- clarification, recovery, and stall counters
- `raw_observations`
- `elicited_hints`
- `turns` (derived `TurnOutput` list)

Counters are control state for the policy. They are not intelligence.

## Goals

The completed and remaining lists partition Sherlock's Observation kinds. See `switchboard/loki/goals.py` for the order and the four dialogue gates. Completing `claimed_company` means the caller named an organization. It does not mean the organization is real.
