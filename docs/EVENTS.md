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
    "goals_remaining": ["pretext_category", "claimed_company"],
    "confidence": 0.55,
    "reason": "Caller greeted without a request.",
    "elicited_hints": []
  }
}
```

`goals_remaining` in a real event lists every Sherlock kind not yet completed. The sample is abbreviated.

`raw_caller_utterance` is the verbatim caller text. `turn` is the strategy decision. `turn.confidence` is strategy-decision confidence, not extraction confidence. `turn.elicited_hints` are unverified breadcrumbs, not Observations. Consumers that synthesize speech use `turn.response_text` only. Sherlock grounds the raw string itself.
