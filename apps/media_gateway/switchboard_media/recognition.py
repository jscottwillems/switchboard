"""Turn one audio frame into finals and publish speech.segment.final.

Owner: ECHO. The socket calls this once per frame. SB-008 speaks from `finals`
and does not call `push_audio` again.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from switchboard_events import EventBus, build_envelope
from switchboard_schemas.enums import EventType, Producer, Speaker
from switchboard_schemas.events import EventEnvelope, SpeechSegmentPayload

from switchboard_media.events import event_bus, publish_validated
from switchboard_media.ports import MockStt, SttEvent, SttPort

_stt: SttPort = MockStt()


@dataclass(frozen=True)
class RecognizedFinal:
    """One non-empty final from this frame, whether or not the publish landed."""

    event: SttEvent
    transcript_segment_id: UUID
    speech_event_id: UUID
    published: bool


@dataclass(frozen=True)
class RecognitionResult:
    events: list[SttEvent]
    next_sequence: int
    finals: tuple[RecognizedFinal, ...] = ()


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
    finals: list[RecognizedFinal] = []
    for event in events:
        if not event.is_final or event.text == "":
            continue
        if publisher is None:
            publisher = event_bus()
        segment_id = uuid4()
        envelope = _final_envelope(
            call_session_id=call_session_id,
            event=event,
            sequence=next_sequence,
            transcript_segment_id=segment_id,
        )
        result = publish_validated(publisher, envelope)
        if not result.failed:
            next_sequence += 1
        finals.append(
            RecognizedFinal(
                event=event,
                transcript_segment_id=segment_id,
                speech_event_id=envelope.event_id,
                published=not result.failed,
            )
        )
    return RecognitionResult(events=events, next_sequence=next_sequence, finals=tuple(finals))


def _final_envelope(
    *,
    call_session_id: UUID,
    event: SttEvent,
    sequence: int,
    transcript_segment_id: UUID,
) -> EventEnvelope:
    return build_envelope(
        event_type=EventType.SPEECH_SEGMENT_FINAL,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=call_session_id,
        payload=SpeechSegmentPayload(
            transcript_segment_id=transcript_segment_id,
            speaker=Speaker.CALLER,
            text=event.text,
            is_final=True,
            stt_confidence=event.stt_confidence,
            start_offset_ms=event.start_offset_ms,
            end_offset_ms=event.end_offset_ms,
            sequence=sequence,
        ),
    )
