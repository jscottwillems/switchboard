# Events

LOKI defines one event. No bus is running in this repository. An orchestrator can publish the object below when it wires telephony.

## `loki.turn.completed`

Emitted after each policy step. Model: `switchboard.loki.handoff.TurnCompletedEvent`.

```json
{
  "event": "loki.turn.completed",
  "session_id": "call-1",
  "turn_index": 0,
  "raw_caller_utterance": "verbatim caller text",
  "turn": {
    "response_text": "Hi. What's this call about?",
    "state": "PURPOSE_DISCOVERY",
    "state_transition": "OPENING -> PURPOSE_DISCOVERY",
    "goals_completed": [],
    "goals_remaining": ["purpose", "organization", "offer", "stable_identifier"],
    "confidence": 0.55,
    "reason": "Caller greeted without a request."
  }
}
```

`raw_caller_utterance` is the observation. `turn` is the derived decision. Consumers that synthesize speech use `turn.response_text` only. Consumers that extract intelligence keep the raw string and may read `turn.goals_*` as LOKI's goal state, not as Sherlock's final record.
