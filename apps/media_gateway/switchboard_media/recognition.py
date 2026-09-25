"""Turn one audio frame into finals and publish speech.segment.final.

Owner: ECHO. The socket calls this. It does not select a reply or synthesize.
That remains SB-008, which should use these finals instead of calling STT again.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import ValidationError

from switchboard_events import EventBus, PublishResult, build_envelope
from switchboard_observability import log_info
from switchboard_schemas.enums import EventType, Producer, Speaker
from switchboard_schemas.events import EventEnvelope, SpeechSegmentPayload

from switchboard_media.events import event_bus
from switchboard_media.ports import MockStt, SttEvent, SttPort

_stt: SttPort = MockStt()


@dataclass(frozen=True)
class RecognitionResult:
    events: list[SttEvent]
    next_sequence: int


def recognize_frame(
    call_session_id: UUID,
    payload: bytes,
    *,
    sequence: int,
    stt: SttPort | None = None,
    bus: EventBus | None = None,
) -> RecognitionResult:
    """Recognize one frame. Publish each non-empty final. Return the next sequence.

    Partials and empty text are not published. A failed publish does not raise
    and does not advance `sequence`. Audio bytes are not placed on the envelope.
    """

    port = _stt if stt is None else stt
    events = port.push_audio(payload)
    next_sequence = sequence
    publisher = bus
    for event in events:
        if not event.is_final or event.text == "":
            continue
        if publisher is None:
            publisher = event_bus()
        result = _publish(
            publisher,
            _final_envelope(
                call_session_id=call_session_id,
                event=event,
                sequence=next_sequence,
            ),
        )
        if not result.failed:
            next_sequence += 1
    return RecognitionResult(events=events, next_sequence=next_sequence)


def _final_envelope(
    *,
    call_session_id: UUID,
    event: SttEvent,
    sequence: int,
) -> EventEnvelope:
    return build_envelope(
        event_type=EventType.SPEECH_SEGMENT_FINAL,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=call_session_id,
        payload=SpeechSegmentPayload(
            transcript_segment_id=uuid4(),
            speaker=Speaker.CALLER,
            text=event.text,
            is_final=True,
            stt_confidence=event.stt_confidence,
            start_offset_ms=event.start_offset_ms,
            end_offset_ms=event.end_offset_ms,
            sequence=sequence,
        ),
    )


def _publish(bus: EventBus, envelope: EventEnvelope) -> PublishResult:
    """Publish a validated envelope. A down Redis leaves the socket up."""

    try:
        return bus.publish(envelope)
    except ValidationError:
        raise
    except (OSError, ValueError):
        log_info(
            "event_publish_failed",
            event_type=envelope.event_type.value,
            event_id=str(envelope.event_id),
            call_session_id=str(envelope.call_session_id),
            reason="redis_unavailable",
        )
        return PublishResult(stream_id=None, failed=True)
