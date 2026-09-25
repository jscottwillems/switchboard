"""Consumer for group intelligence.extractor. Owner: SHERLOCK.

`speech.segment.final` becomes `interp.intelligence_finding` rows and
`intelligence.finding.proposed`. Other envelopes are acknowledged so the
group does not stall. Extractor failures are logged and acknowledged.
They are not raised to the caller, and this module does not import the
media gateway.
"""

import os
import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from uuid import UUID, uuid5

from switchboard_classification import E164FindingExtractor, FindingExtractor
from switchboard_events import ConsumerGroup, DeliveredEvent, EventBus, build_envelope
from switchboard_observability import log_info
from switchboard_repositories import FindingWriter
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import EventType, Producer, TranscriptSource
from switchboard_schemas.events import EventEnvelope, IntelligenceFindingProposed, SpeechSegmentPayload
from switchboard_schemas.interpretations import IntelligenceFinding
from switchboard_schemas.observations import TranscriptSegment

from switchboard_intelligence.deps import event_bus, open_finding_writer
from switchboard_intelligence.settings import get_settings

# The final-segment payload has no recognizer id and no media stream id.
# The API projector writes obs.transcript_segment. This object is only the
# extractor input, and it is not inserted.
_SEGMENT_PROVIDER = "stt"
_GROUP = ConsumerGroup.INTELLIGENCE_EXTRACTOR

WriterFactory = Callable[[], AbstractContextManager[FindingWriter]]


@dataclass(frozen=True)
class PollResult:
    """One read. `retry` means an entry was left pending after a write failure."""

    acknowledged: int
    retry: bool


def extractor_worker_enabled() -> bool:
    """The HTTP process starts the loop unless tests or the env flag turn it off."""

    flag = os.environ.get("SWITCHBOARD_EXTRACTOR_WORKER", "")
    if flag == "0":
        return False
    if flag == "1":
        return True
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    settings = get_settings()
    return bool(settings.redis_url and settings.database_url)


def transcript_from_final(envelope: EventEnvelope, payload: SpeechSegmentPayload) -> TranscriptSegment:
    """Adapt a final speech payload to the extractor's segment input.

    `stt_confidence` is copied onto the segment only. Finding confidence is
    chosen by the extractor.
    """

    return TranscriptSegment(
        id=payload.transcript_segment_id,
        call_session_id=envelope.call_session_id,
        media_stream_id=_placeholder_media_stream_id(payload.transcript_segment_id),
        sequence=payload.sequence,
        speaker=payload.speaker,
        source=TranscriptSource.STT,
        text=payload.text,
        start_offset_ms=payload.start_offset_ms,
        end_offset_ms=payload.end_offset_ms,
        is_final=True,
        stt_confidence=payload.stt_confidence,
        provider=_SEGMENT_PROVIDER,
        created_at=envelope.occurred_at,
    )


def finding_proposed_envelope(finding: IntelligenceFinding, source: EventEnvelope) -> EventEnvelope:
    """One proposed event per finding. The id is stable across redelivery.

    `confidence` is the finding's confidence, never the speech payload's
    `stt_confidence`.
    """

    return build_envelope(
        event_type=EventType.INTELLIGENCE_FINDING_PROPOSED,
        producer=Producer.INTELLIGENCE,
        call_session_id=finding.call_session_id,
        payload=IntelligenceFindingProposed(
            finding_id=finding.id,
            kind=finding.kind,
            value=finding.value,
            confidence=finding.confidence,
            extractor=finding.extractor,
            extractor_version=finding.extractor_version,
        ),
        occurred_at=source.occurred_at,
        event_id=_proposed_event_id(finding.id),
        causation_id=source.event_id,
    )


class ExtractorConsumer:
    """Read `intelligence.extractor`, write findings, publish proposals."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        extractor: FindingExtractor | None = None,
        open_writer: WriterFactory | None = None,
        consumer_name: str = "extractor",
    ) -> None:
        self._bus = event_bus() if bus is None else bus
        self._extractor = E164FindingExtractor() if extractor is None else extractor
        self._open_writer = open_finding_writer if open_writer is None else open_writer
        self._consumer_name = consumer_name

    def poll(self, *, count: int = 16, block_ms: int | None = None) -> PollResult:
        """Handle one batch. Extractor failures are acknowledged inside `handle`."""

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
        """Process one entry. True means the caller should acknowledge it.

        False leaves the entry pending so a failed write can be retried.
        An extractor exception is acknowledged and the finding is omitted.
        """

        envelope = delivered.envelope
        if envelope.event_type is not EventType.SPEECH_SEGMENT_FINAL:
            return True
        try:
            findings = self._extract(envelope)
        except Exception:
            _log_extractor_failure(envelope)
            return True
        if not findings:
            return True
        try:
            stored = self._insert(findings)
        except Exception as exc:
            _log_write_failure(envelope, exc)
            return False
        for finding in stored:
            result = self._bus.publish(finding_proposed_envelope(finding, envelope))
            if result.failed:
                return False
        return True

    def _extract(self, envelope: EventEnvelope) -> list[IntelligenceFinding]:
        payload = SpeechSegmentPayload.model_validate(envelope.payload)
        if not payload.is_final:
            raise ValueError("speech.segment.final requires is_final true")
        return list(self._extractor.extract([transcript_from_final(envelope, payload)]))

    def _insert(self, findings: Sequence[IntelligenceFinding]) -> list[IntelligenceFinding]:
        with self._open_writer() as writer:
            stored: list[IntelligenceFinding] = []
            for finding in findings:
                row, _created = writer.findings().insert(finding)
                stored.append(row)
            return stored


def serve_extractor(stop: threading.Event) -> None:
    """Block until `stop` is set. Redis errors stay in this loop."""

    log_info("extractor_worker_started", group=_GROUP.value)
    consumer = ExtractorConsumer()
    while not stop.is_set():
        try:
            result = consumer.poll(block_ms=500)
        except Exception:
            log_info("extractor_poll_failed", group=_GROUP.value, reason="consumer_exception")
            stop.wait(0.25)
            continue
        if result.retry:
            stop.wait(0.25)
    log_info("extractor_worker_stopped", group=_GROUP.value)


def _placeholder_media_stream_id(segment_id: UUID) -> UUID:
    return uuid5(SWITCHBOARD_ID_NAMESPACE, f"speech.segment.final|{segment_id}|media")


def _proposed_event_id(finding_id: UUID) -> UUID:
    return uuid5(SWITCHBOARD_ID_NAMESPACE, f"intelligence.finding.proposed|{finding_id}")


def _log_extractor_failure(envelope: EventEnvelope) -> None:
    log_info(
        "extractor_failed",
        event_id=str(envelope.event_id),
        event_type=envelope.event_type.value,
        call_session_id=str(envelope.call_session_id),
        reason="extractor_exception",
    )


def _log_write_failure(envelope: EventEnvelope, exc: Exception) -> None:
    log_info(
        "extractor_write_failed",
        event_id=str(envelope.event_id),
        event_type=envelope.event_type.value,
        call_session_id=str(envelope.call_session_id),
        reason="repository_exception",
        error_type=type(exc).__name__,
    )
