# Events

Contract version **0.1.0**. Durable facts and judgments cross process boundaries as `EventEnvelope` records. Audio frames do not.

## Transport

| Item | Value |
| --- | --- |
| Bus | Redis stream |
| Key | `switchboard.events` |
| Write | `XADD` with approximate maxlen 100000 |
| Delivery | At least once, via consumer groups |
| Envelope | `EventEnvelope` in `packages/schemas` |
| Payload check | `validate_event` must succeed before publish |

Consumer groups:

| Group | Process | Writes |
| --- | --- | --- |
| `api.projector` | `apps/api` | `obs.*` and `interp.conversation_turn` |
| `intelligence.extractor` | `apps/intelligence` | `interp.intelligence_finding` |
| `intelligence.correlator` | `apps/intelligence` | `attr.*` |

The skeleton does not publish or consume yet (`SB-016`).

Consumers dedupe on `event_id`. Ordering on the stream is global and best-effort across calls. Handlers are idempotent.

`event_version` is `1`. A breaking payload change bumps `event_version` or adds a new `event_type`. It does not reuse a name.

## Envelope

| Field | Meaning |
| --- | --- |
| `event_id` | Unique id of this message |
| `event_type` | One of `EventType` |
| `event_version` | `1` |
| `occurred_at` | Timezone-aware timestamp |
| `producer` | `api`, `media_gateway`, or `intelligence` |
| `call_session_id` | Call this event is about. Campaign events use the call that triggered them |
| `causation_id` | `event_id` of the cause, or null |
| `payload` | Object validated by the model registered for `event_type` |

`speech.segment.partial` requires payload `is_final: false`. `speech.segment.final` requires `is_final: true`.

## Taxonomy

| Event | Payload model | Producer | Consumers | Projector effect |
| --- | --- | --- | --- | --- |
| `telephony.call.received` | `TelephonyCallReceived` | api | api.projector | Insert `obs.call_session` in `ringing` |
| `telephony.call.answered` | `TelephonyCallAnswered` | api | api.projector | Set session `in_progress` and `answered_at` |
| `telephony.call.completed` | `TelephonyCallCompleted` | api | api.projector, intelligence.extractor | Set session `completed` |
| `telephony.call.failed` | `TelephonyCallFailed` | api | api.projector | Set session `failed` |
| `media.stream.started` | `MediaStreamStarted` | media_gateway | api.projector | Insert `obs.media_stream` |
| `media.stream.stopped` | `MediaStreamStopped` | media_gateway | api.projector | Close the media row |
| `media.stream.failed` | `MediaStreamFailed` | media_gateway | api.projector | Fail the media row |
| `speech.segment.partial` | `SpeechSegmentPayload` | media_gateway | none in MVP | No database write |
| `speech.segment.final` | `SpeechSegmentPayload` | media_gateway | api.projector, intelligence.extractor | Insert `obs.transcript_segment` (`source: stt`) |
| `speech.synthesis.requested` | `SpeechSynthesisRequested` | media_gateway | api.projector | Insert honeypot `tts_input` segment when paired with completion |
| `speech.synthesis.completed` | `SpeechSynthesisCompleted` | media_gateway | api.projector | Mark synthesis duration on the turn projection |
| `speech.synthesis.failed` | `SpeechSynthesisFailed` | media_gateway | api.projector | Record `end_reason` on the stream or turn projection |
| `conversation.response.selected` | `ConversationResponseSelected` | media_gateway | api.projector | Feeds the honeypot turn |
| `conversation.turn.recorded` | `ConversationTurnRecorded` | media_gateway | api.projector | Insert `interp.conversation_turn` |
| `intelligence.finding.proposed` | `IntelligenceFindingProposed` | intelligence | intelligence.correlator, api.projector | Extractor also inserts `interp.intelligence_finding` itself |
| `campaign.opened` | `CampaignOpened` | intelligence | api read model via the writer | Correlator inserts `attr.campaign` |
| `campaign.attribution.proposed` | `CampaignAttributionProposed` | intelligence | api read model via the writer | Correlator inserts `attr.campaign_attribution` |

`stt_confidence` on a speech payload is the recognizer's score. It is copied onto `obs.transcript_segment.stt_confidence` only. It is never copied into `IntelligenceFinding.confidence` or `CampaignAttribution.confidence`.

## What is not an event

- Inbound or outbound audio frames
- WebSocket `ready`, `mark`, and `clear`
- `ResponseRequest` / `ResponseDecision` (in-process)
- Dashboard polls
- Health checks

Partial transcripts may be emitted for a future live view. The MVP projector ignores them so a revised partial cannot overwrite a stored observation. Final segments are immutable once written.

## Publisher duties

The publisher fills `event_id`, `occurred_at`, `producer`, and `call_session_id`, validates the payload, and only then writes the stream. A publish failure is logged with `log_info` field names that survive `safe_fields`. The hot path does not wait on the projector's database transaction.

Crash between a database commit and a publish can drop an event in 0.1.0. That gap is accepted in ADR-011. Consumers must tolerate a missing event without corrupting rows they already wrote.
