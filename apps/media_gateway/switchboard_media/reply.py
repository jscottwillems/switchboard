"""Publish the conversation events for one recognized frame. Owner: ECHO.

The socket calls `respond_to_audio` for the audio, then this module publishes
the decision. A failed publish does not raise.
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

from switchboard_events import EventBus, build_envelope
from switchboard_schemas.enums import EventType, Producer, Speaker
from switchboard_schemas.events import ConversationResponseSelected, ConversationTurnRecorded
from switchboard_schemas.hotpath import ResponseDecision

from switchboard_media.events import event_bus, publish_validated
from switchboard_media.recognition import RecognizedFinal

# A caller turn is a grouping of finals, not a selector decision.
CALLER_TURN_CONFIDENCE = 1.0


def record_exchange(
    call_session_id: UUID,
    turn_index: int,
    finals: Sequence[RecognizedFinal],
    decision: ResponseDecision,
    *,
    bus: EventBus | None = None,
) -> int:
    """Publish the caller turn, the selected reply, and the honeypot turn.

    `turn_index` is the caller turn. The honeypot turn uses the next index.
    Returns the index to use for the next exchange. Redis failures are logged
    and do not raise.
    """

    if not finals:
        return turn_index
    publisher = event_bus() if bus is None else bus
    segment_ids = [final.transcript_segment_id for final in finals]
    cause = finals[-1].speech_event_id
    caller_id = uuid4()
    honeypot_id = uuid4()
    caller = build_envelope(
        event_type=EventType.CONVERSATION_TURN_RECORDED,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=call_session_id,
        causation_id=cause,
        payload=ConversationTurnRecorded(
            turn_id=caller_id,
            turn_index=turn_index,
            speaker=Speaker.CALLER,
            text=finals[-1].event.text,
            transcript_segment_ids=segment_ids,
            strategy_id=None,
            confidence=CALLER_TURN_CONFIDENCE,
        ),
    )
    selected = build_envelope(
        event_type=EventType.CONVERSATION_RESPONSE_SELECTED,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=call_session_id,
        causation_id=cause,
        payload=ConversationResponseSelected(
            turn_id=honeypot_id,
            strategy_id=decision.strategy_id,
            text=decision.text,
            confidence=decision.confidence,
        ),
    )
    honeypot = build_envelope(
        event_type=EventType.CONVERSATION_TURN_RECORDED,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=call_session_id,
        causation_id=selected.event_id,
        payload=ConversationTurnRecorded(
            turn_id=honeypot_id,
            turn_index=turn_index + 1,
            speaker=Speaker.HONEYPOT,
            text=decision.text,
            transcript_segment_ids=segment_ids,
            strategy_id=decision.strategy_id,
            confidence=decision.confidence,
        ),
    )
    publish_validated(publisher, caller)
    publish_validated(publisher, selected)
    publish_validated(publisher, honeypot)
    return turn_index + 2
