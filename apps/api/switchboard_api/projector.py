"""Consumer for group api.projector. Owner: ATLAS.

`speech.segment.final` becomes `obs.transcript_segment`.
`conversation.turn.recorded` becomes `interp.conversation_turn`.
The webhook already wrote the call session, and the extractor already wrote
findings, so those events are acknowledged and not inserted again.

`speech.segment.final` has no media stream id. The segment's foreign key
needs a row, so the first transcript for a call inserts one
`obs.media_stream` with `external_stream_id` `unscoped` when the call has
none yet. A stream already stored for that call is reused.
"""

import os
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal, Never
from uuid import UUID, uuid5

from pydantic import ValidationError

from switchboard_events import ConsumerGroup, DeliveredEvent, EventBus
from switchboard_observability import log_info
from switchboard_repositories import ObservationWriter
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import EventType, MediaStreamState, TranscriptSource
from switchboard_schemas.events import ConversationTurnRecorded, EventEnvelope, SpeechSegmentPayload
from switchboard_schemas.interpretations import ConversationTurn
from switchboard_schemas.observations import MediaStream, TranscriptSegment

from switchboard_api.deps import get_event_bus, open_observation_writer

# DATA_MODEL names the mock recognizer. It is not on SpeechSegmentPayload.
_TRANSCRIPT_PROVIDER = "mock-stt"
_UNSCOPED_EXTERNAL_STREAM_ID = "unscoped"
_UNSCOPED_ENCODING: Literal["audio/pcmu"] = "audio/pcmu"
_UNSCOPED_SAMPLE_RATE_HZ = 8000
_GROUP = ConsumerGroup.API_PROJECTOR

WriterFactory = Callable[[], AbstractContextManager[ObservationWriter]]


@dataclass(frozen=True)
class PollResult:
    """One read. `retry` means an entry was left pending after a write failure."""

    acknowledged: int
    retry: bool


def projector_worker_enabled() -> bool:
    """The HTTP process starts the loop unless tests or the env flag turn it off.

    Defaults in `get_settings` are not enough. The loop starts only when
    `DATABASE_URL` and `REDIS_URL` are set in the environment, matching the
    compose file.
    """

    flag = os.environ.get("SWITCHBOARD_PROJECTOR_WORKER", "")
    if flag == "0":
        return False
    if flag == "1":
        return True
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    return bool(os.environ.get("DATABASE_URL") and os.environ.get("REDIS_URL"))


def unscoped_media_stream_id(call_session_id: UUID) -> UUID:
    """Stable id for the stream row a final segment can cite."""

    return uuid5(
        SWITCHBOARD_ID_NAMESPACE,
        f"obs.media_stream|{call_session_id}|{_UNSCOPED_EXTERNAL_STREAM_ID}",
    )


class ProjectorConsumer:
    """Read `api.projector` and write transcripts and turns."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        open_writer: WriterFactory | None = None,
        consumer_name: str = "projector",
    ) -> None:
        self._bus = get_event_bus() if bus is None else bus
        self._open_writer = open_observation_writer if open_writer is None else open_writer
        self._consumer_name = consumer_name

    def poll(self, *, count: int = 16, block_ms: int | None = None) -> PollResult:
        """Handle one batch. A failed write leaves that entry pending."""

        delivered = self._bus.read(
            _GROUP,
            self._consumer_name,
            count=count,
            block_ms=block_ms,
        )
        acknowledged = 0
        for item in delivered:
            if not self.handle(item):
                return PollResult(acknowledged=acknowledged, retry=True)
            self._bus.ack(_GROUP, item)
            acknowledged += 1
        return PollResult(acknowledged=acknowledged, retry=False)

    def handle(self, delivered: DeliveredEvent) -> bool:
        """Process one entry. True means the caller should acknowledge it."""

        envelope = delivered.envelope
        match envelope.event_type:
            case EventType.SPEECH_SEGMENT_FINAL:
                return self._project_transcript(envelope)
            case EventType.CONVERSATION_TURN_RECORDED:
                return self._project_turn(envelope)
            case (
                EventType.TELEPHONY_CALL_RECEIVED
                | EventType.TELEPHONY_CALL_ANSWERED
                | EventType.TELEPHONY_CALL_COMPLETED
                | EventType.TELEPHONY_CALL_FAILED
                | EventType.MEDIA_STREAM_STARTED
                | EventType.MEDIA_STREAM_STOPPED
                | EventType.MEDIA_STREAM_FAILED
                | EventType.SPEECH_SEGMENT_PARTIAL
                | EventType.SPEECH_SYNTHESIS_REQUESTED
                | EventType.SPEECH_SYNTHESIS_COMPLETED
                | EventType.SPEECH_SYNTHESIS_FAILED
                | EventType.CONVERSATION_RESPONSE_SELECTED
                | EventType.INTELLIGENCE_FINDING_PROPOSED
                | EventType.CAMPAIGN_OPENED
                | EventType.CAMPAIGN_ATTRIBUTION_PROPOSED
            ):
                return True
            case _ as unreachable:
                return _never(unreachable)

    def _project_transcript(self, envelope: EventEnvelope) -> bool:
        try:
            payload = SpeechSegmentPayload.model_validate(envelope.payload)
        except ValidationError:
            _log_skip(envelope, "invalid_payload")
            return True
        if not payload.is_final:
            return True
        try:
            with self._open_writer() as writer:
                media_stream_id = _ensure_media_stream(writer, envelope)
                writer.transcripts().insert(_segment(envelope, payload, media_stream_id))
        except Exception as exc:
            _log_write_failure(envelope, exc)
            return False
        return True

    def _project_turn(self, envelope: EventEnvelope) -> bool:
        try:
            payload = ConversationTurnRecorded.model_validate(envelope.payload)
        except ValidationError:
            _log_skip(envelope, "invalid_payload")
            return True
        try:
            with self._open_writer() as writer:
                writer.conversation_turns().insert(_turn(envelope, payload))
        except Exception as exc:
            _log_write_failure(envelope, exc)
            return False
        return True


def serve_projector(stop: threading.Event) -> None:
    """Block until `stop` is set. Redis errors stay in this loop."""

    log_info("projector_worker_started", group=_GROUP.value)
    consumer = ProjectorConsumer()
    while not stop.is_set():
        try:
            result = consumer.poll(block_ms=500)
        except Exception:
            log_info("projector_poll_failed", group=_GROUP.value, reason="consumer_exception")
            stop.wait(0.25)
            continue
        if result.retry:
            stop.wait(0.25)
    log_info("projector_worker_stopped", group=_GROUP.value)


def _ensure_media_stream(writer: ObservationWriter, envelope: EventEnvelope) -> UUID:
    existing = writer.media_streams().list_for_session(envelope.call_session_id)
    if existing:
        return existing[0].id
    stream, _created = writer.media_streams().insert(
        MediaStream(
            id=unscoped_media_stream_id(envelope.call_session_id),
            call_session_id=envelope.call_session_id,
            external_stream_id=_UNSCOPED_EXTERNAL_STREAM_ID,
            encoding=_UNSCOPED_ENCODING,
            sample_rate_hz=_UNSCOPED_SAMPLE_RATE_HZ,
            state=MediaStreamState.STREAMING,
            started_at=envelope.occurred_at,
        )
    )
    return stream.id


def _segment(
    envelope: EventEnvelope,
    payload: SpeechSegmentPayload,
    media_stream_id: UUID,
) -> TranscriptSegment:
    return TranscriptSegment(
        id=payload.transcript_segment_id,
        call_session_id=envelope.call_session_id,
        media_stream_id=media_stream_id,
        sequence=payload.sequence,
        speaker=payload.speaker,
        source=TranscriptSource.STT,
        text=payload.text,
        start_offset_ms=payload.start_offset_ms,
        end_offset_ms=payload.end_offset_ms,
        is_final=True,
        stt_confidence=payload.stt_confidence,
        provider=_TRANSCRIPT_PROVIDER,
        created_at=envelope.occurred_at,
    )


def _turn(envelope: EventEnvelope, payload: ConversationTurnRecorded) -> ConversationTurn:
    return ConversationTurn(
        id=payload.turn_id,
        call_session_id=envelope.call_session_id,
        turn_index=payload.turn_index,
        speaker=payload.speaker,
        text=payload.text,
        transcript_segment_ids=list(payload.transcript_segment_ids),
        strategy_id=payload.strategy_id,
        confidence=payload.confidence,
        created_at=envelope.occurred_at,
    )


def _never(event_type: Never) -> bool:
    raise AssertionError(f"unhandled event type: {event_type}")


def _log_skip(envelope: EventEnvelope, reason: str) -> None:
    log_info(
        "projector_skipped",
        event_id=str(envelope.event_id),
        event_type=envelope.event_type.value,
        call_session_id=str(envelope.call_session_id),
        reason=reason,
    )


def _log_write_failure(envelope: EventEnvelope, exc: Exception) -> None:
    log_info(
        "projector_write_failed",
        event_id=str(envelope.event_id),
        event_type=envelope.event_type.value,
        call_session_id=str(envelope.call_session_id),
        reason="repository_exception",
        error_type=type(exc).__name__,
    )
