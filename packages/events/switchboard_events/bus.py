"""Publish and consume EventEnvelope records on Redis stream switchboard.events.

The stream entry has one field, `envelope`, whose value is the JSON envelope.
XADD uses an approximate maxlen of 100000. Publish dedupes on event_id.
A Redis failure is logged and returned. It is not raised, so a caller that
already committed Postgres work does not roll that work back (ADR-011).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Never
from uuid import UUID, uuid4

import redis
from pydantic import ValidationError
from redis.exceptions import RedisError, ResponseError

from switchboard_observability import log_info
from switchboard_schemas.common import ContractModel
from switchboard_schemas.enums import EventType, Producer
from switchboard_schemas.events import EventEnvelope, validate_event

from switchboard_events.groups import ConsumerGroup

STREAM_KEY = "switchboard.events"
STREAM_MAXLEN = 100_000
ENVELOPE_FIELD = "envelope"

_PUBLISH_LUA = """
local existing = redis.call('GET', KEYS[1])
if existing then
  return {'duplicate', existing}
end
local id = redis.call('XADD', KEYS[2], 'MAXLEN', '~', ARGV[2], '*', 'envelope', ARGV[1])
redis.call('SET', KEYS[1], id)
return {'published', id}
"""


@dataclass(frozen=True)
class PublishResult:
    """Outcome of one publish attempt. `failed` means the stream was not written."""

    stream_id: str | None
    duplicate: bool = False
    failed: bool = False


@dataclass(frozen=True)
class DeliveredEvent:
    """One stream entry a consumer group has reserved and this process has validated."""

    stream_id: str
    envelope: EventEnvelope


def build_envelope(
    *,
    event_type: EventType,
    producer: Producer,
    call_session_id: UUID,
    payload: ContractModel,
    occurred_at: datetime | None = None,
    event_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope:
    """Fill publisher fields, validate the payload, and return the envelope."""

    when = occurred_at if occurred_at is not None else datetime.now(timezone.utc)
    envelope = EventEnvelope(
        event_id=event_id if event_id is not None else uuid4(),
        event_type=event_type,
        event_version=1,
        occurred_at=when,
        producer=producer,
        call_session_id=call_session_id,
        causation_id=causation_id,
        payload=payload.model_dump(mode="json"),
    )
    return validate_event(envelope)


def publish_dedupe_key(event_id: UUID) -> str:
    return f"switchboard.events:id:{event_id}"


def consume_dedupe_key(group: ConsumerGroup, event_id: UUID) -> str:
    return f"switchboard.events:ack:{group.value}:{event_id}"


class EventBus:
    """Shared publisher and consumer-group reader.

    Construct one per process from `REDIS_URL`. Connections are opened per call
    and closed before return. Publish never waits for a projector transaction.
    """

    def __init__(self, redis_url: str, *, socket_timeout_seconds: float = 0.5) -> None:
        self._redis_url = redis_url
        self._timeout = socket_timeout_seconds

    def publish(self, envelope: EventEnvelope) -> PublishResult:
        """Validate, then XADD. The same event_id does not append a second entry.

        Redis and socket failures are logged with `event_publish_failed` and
        returned as `failed=True`. Validation errors propagate.
        """

        validate_event(envelope)
        try:
            client = self._connect(block_ms=None)
            try:
                raw = client.eval(
                    _PUBLISH_LUA,
                    2,
                    publish_dedupe_key(envelope.event_id),
                    STREAM_KEY,
                    envelope.model_dump_json(),
                    str(STREAM_MAXLEN),
                )
            finally:
                client.close()
        except (RedisError, OSError):
            self._log_publish_failure(envelope, "redis_unavailable")
            return PublishResult(stream_id=None, duplicate=False, failed=True)
        return self._publish_result(envelope, raw)

    def ensure_group(self, group: ConsumerGroup) -> None:
        """Create the group at stream id 0 so entries already on the stream are visible."""

        client = self._connect(block_ms=None)
        try:
            self._ensure_group(client, group)
        finally:
            client.close()

    def read(
        self,
        group: ConsumerGroup,
        consumer: str,
        *,
        count: int = 16,
        block_ms: int | None = None,
    ) -> list[DeliveredEvent]:
        """Read pending entries for this consumer, otherwise new entries.

        Invalid envelopes are acknowledged and omitted so one poison entry
        cannot stall the group. Entries whose event_id was already acknowledged
        for this group are acknowledged again and omitted.
        Redis failures are logged and raised. This path is not the call hot path.
        """

        if count < 1:
            raise ValueError("count must be at least 1")
        if consumer == "":
            raise ValueError("consumer name is required")
        if block_ms is not None and block_ms < 1:
            raise ValueError("block_ms must be a positive number of milliseconds")
        client = self._connect(block_ms=block_ms)
        try:
            self._ensure_group(client, group)
            pending = self._accept(
                client,
                group,
                self._xread(client, group, consumer, "0", count, block=False),
            )
            if pending:
                return pending
            return self._accept(
                client,
                group,
                self._xread(
                    client,
                    group,
                    consumer,
                    ">",
                    count,
                    block=block_ms is not None,
                    block_ms=block_ms,
                ),
            )
        except (RedisError, OSError):
            log_info(
                "event_read_failed",
                group=group.value,
                reason="redis_unavailable",
            )
            raise
        finally:
            client.close()

    def ack(self, group: ConsumerGroup, delivered: DeliveredEvent) -> None:
        """Remember event_id for this group, then XACK the stream entry."""

        client = self._connect(block_ms=None)
        try:
            client.set(
                consume_dedupe_key(group, delivered.envelope.event_id),
                delivered.stream_id,
            )
            client.xack(STREAM_KEY, group.value, delivered.stream_id)
        finally:
            client.close()

    def _connect(self, *, block_ms: int | None) -> redis.Redis:
        socket_timeout = self._timeout
        if block_ms is not None:
            socket_timeout = self._timeout + (block_ms / 1000)
        return redis.Redis.from_url(
            self._redis_url,
            socket_connect_timeout=self._timeout,
            socket_timeout=socket_timeout,
            decode_responses=True,
        )

    def _ensure_group(self, client: redis.Redis, group: ConsumerGroup) -> None:
        _known_group(group)
        try:
            client.xgroup_create(STREAM_KEY, group.value, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def _xread(
        self,
        client: redis.Redis,
        group: ConsumerGroup,
        consumer: str,
        stream_id: str,
        count: int,
        *,
        block: bool,
        block_ms: int | None = None,
    ) -> list[tuple[str, dict[str, str]]]:
        if block and block_ms is None:
            raise ValueError("block_ms is required when blocking")
        if block:
            response = client.xreadgroup(
                group.value,
                consumer,
                {STREAM_KEY: stream_id},
                count=count,
                block=block_ms,
            )
        else:
            response = client.xreadgroup(
                group.value,
                consumer,
                {STREAM_KEY: stream_id},
                count=count,
            )
        return _entries(response)

    def _accept(
        self,
        client: redis.Redis,
        group: ConsumerGroup,
        entries: list[tuple[str, dict[str, str]]],
    ) -> list[DeliveredEvent]:
        delivered: list[DeliveredEvent] = []
        for stream_id, fields in entries:
            raw = fields.get(ENVELOPE_FIELD)
            if raw is None:
                self._drop_invalid(client, group, stream_id)
                continue
            try:
                envelope = validate_event(EventEnvelope.model_validate_json(raw))
            except (ValidationError, ValueError):
                self._drop_invalid(client, group, stream_id)
                continue
            if client.get(consume_dedupe_key(group, envelope.event_id)):
                client.xack(STREAM_KEY, group.value, stream_id)
                continue
            delivered.append(DeliveredEvent(stream_id=stream_id, envelope=envelope))
        return delivered

    def _drop_invalid(self, client: redis.Redis, group: ConsumerGroup, stream_id: str) -> None:
        log_info(
            "event_consume_invalid",
            stream_id=stream_id,
            group=group.value,
            reason="invalid_envelope",
        )
        client.xack(STREAM_KEY, group.value, stream_id)

    def _publish_result(self, envelope: EventEnvelope, raw: object) -> PublishResult:
        kind = _text(_pair_item(raw, 0))
        stream_id = _text(_pair_item(raw, 1))
        if kind == "published" and stream_id is not None:
            return PublishResult(stream_id=stream_id, duplicate=False, failed=False)
        if kind == "duplicate" and stream_id is not None:
            return PublishResult(stream_id=stream_id, duplicate=True, failed=False)
        self._log_publish_failure(envelope, "unexpected_publish_result")
        return PublishResult(stream_id=None, duplicate=False, failed=True)

    def _log_publish_failure(self, envelope: EventEnvelope, reason: str) -> None:
        log_info(
            "event_publish_failed",
            event_type=envelope.event_type.value,
            event_id=str(envelope.event_id),
            call_session_id=str(envelope.call_session_id),
            reason=reason,
        )


def _pair_item(raw: object, index: int) -> object:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return raw[index]
    return None


def _text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode()
    return None


def _entries(response: object) -> list[tuple[str, dict[str, str]]]:
    if response is None:
        return []
    if not isinstance(response, list):
        raise TypeError("unexpected XREADGROUP response")
    entries: list[tuple[str, dict[str, str]]] = []
    for stream in response:
        if not isinstance(stream, (list, tuple)) or len(stream) != 2:
            raise TypeError("unexpected XREADGROUP stream")
        _name, messages = stream
        if not messages:
            continue
        if not isinstance(messages, list):
            raise TypeError("unexpected XREADGROUP message list")
        for message in messages:
            if not isinstance(message, (list, tuple)) or len(message) != 2:
                raise TypeError("unexpected XREADGROUP message")
            stream_id, fields = message
            normalized_id = _text(stream_id)
            if normalized_id is None or not isinstance(fields, dict):
                raise TypeError("unexpected XREADGROUP message")
            normalized: dict[str, str] = {}
            for key, value in fields.items():
                key_text = _text(key)
                value_text = _text(value)
                if key_text is None or value_text is None:
                    raise TypeError("unexpected XREADGROUP field")
                normalized[key_text] = value_text
            entries.append((normalized_id, normalized))
    return entries


def _known_group(group: ConsumerGroup) -> None:
    match group:
        case ConsumerGroup.API_PROJECTOR:
            return
        case ConsumerGroup.INTELLIGENCE_EXTRACTOR:
            return
        case ConsumerGroup.INTELLIGENCE_CORRELATOR:
            return
        case _ as unreachable:
            _never(unreachable)


def _never(value: Never) -> Never:
    raise AssertionError(f"unhandled consumer group: {value}")
