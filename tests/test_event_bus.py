"""SB-016: validated publish and consumer-group reads on Redis."""

import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import redis
from pydantic import ValidationError
from redis.exceptions import RedisError

from switchboard_api.settings import get_settings as get_api_settings
from switchboard_events import (
    ENVELOPE_FIELD,
    STREAM_KEY,
    STREAM_MAXLEN,
    ConsumerGroup,
    EventBus,
    build_envelope,
)
from switchboard_events.bus import _PUBLISH_LUA
from switchboard_intelligence.settings import get_settings as get_intelligence_settings
from switchboard_media.settings import get_settings as get_media_settings
from switchboard_schemas.enums import EventType, Producer, Speaker
from switchboard_schemas.events import (
    EventEnvelope,
    SpeechSegmentPayload,
    TelephonyCallAnswered,
    TelephonyCallReceived,
)

NOW = datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def redis_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = "redis://localhost:6379/15"
    client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
    except RedisError as exc:
        pytest.fail(f"SB-016 tests need Redis at {url}: {exc}")
    client.flushdb()
    client.close()
    monkeypatch.setenv("REDIS_URL", url)
    get_api_settings.cache_clear()
    get_intelligence_settings.cache_clear()
    get_media_settings.cache_clear()
    yield url
    get_api_settings.cache_clear()
    get_intelligence_settings.cache_clear()
    get_media_settings.cache_clear()


def _received(call_session_id=None) -> EventEnvelope:
    return build_envelope(
        event_type=EventType.TELEPHONY_CALL_RECEIVED,
        producer=Producer.API,
        call_session_id=call_session_id or uuid4(),
        payload=TelephonyCallReceived(
            external_call_id="demo-1",
            carrier="mock",
            caller_number_e164="+15551212000",
            called_number_e164="+15550001001",
        ),
        occurred_at=NOW,
    )


def test_consumer_group_names_match_the_contract() -> None:
    assert {group.value for group in ConsumerGroup} == {
        "api.projector",
        "intelligence.extractor",
        "intelligence.correlator",
    }
    assert STREAM_KEY == "switchboard.events"
    assert STREAM_MAXLEN == 100_000
    assert "MAXLEN" in _PUBLISH_LUA
    assert "'~'" in _PUBLISH_LUA
    assert "'envelope'" in _PUBLISH_LUA


def test_build_envelope_rejects_a_final_segment_marked_partial() -> None:
    with pytest.raises(ValueError, match="is_final"):
        build_envelope(
            event_type=EventType.SPEECH_SEGMENT_FINAL,
            producer=Producer.MEDIA_GATEWAY,
            call_session_id=uuid4(),
            payload=SpeechSegmentPayload(
                transcript_segment_id=uuid4(),
                speaker=Speaker.CALLER,
                text="hello",
                is_final=False,
                start_offset_ms=0,
                end_offset_ms=10,
                sequence=0,
            ),
            occurred_at=NOW,
        )


def test_invalid_envelope_does_not_open_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("redis opened for an invalid envelope")

    monkeypatch.setattr("switchboard_events.bus.redis.Redis.from_url", fail_open)
    envelope = EventEnvelope(
        event_id=uuid4(),
        event_type=EventType.TELEPHONY_CALL_RECEIVED,
        occurred_at=NOW,
        producer=Producer.API,
        call_session_id=uuid4(),
        payload={"external_call_id": ""},
    )
    with pytest.raises(ValidationError):
        EventBus("redis://localhost:6379/15").publish(envelope)


def test_publish_is_readable_by_each_durable_group(redis_url: str) -> None:
    bus = EventBus(redis_url)
    envelope = _received()
    result = bus.publish(envelope)
    assert result.stream_id
    assert not result.duplicate
    assert not result.failed

    seen: set[str] = set()
    for group, consumer in (
        (ConsumerGroup.API_PROJECTOR, "api-1"),
        (ConsumerGroup.INTELLIGENCE_EXTRACTOR, "sherlock-1"),
        (ConsumerGroup.INTELLIGENCE_CORRELATOR, "watson-1"),
    ):
        delivered = bus.read(group, consumer)
        assert len(delivered) == 1
        assert delivered[0].stream_id == result.stream_id
        assert delivered[0].envelope.event_id == envelope.event_id
        assert delivered[0].envelope.event_type is EventType.TELEPHONY_CALL_RECEIVED
        assert delivered[0].envelope.payload["external_call_id"] == "demo-1"
        seen.add(group.value)
        bus.ack(group, delivered[0])
        assert bus.read(group, consumer) == []
    assert seen == {group.value for group in ConsumerGroup}


def test_republish_of_the_same_event_id_does_not_append(redis_url: str) -> None:
    bus = EventBus(redis_url)
    envelope = _received()
    first = bus.publish(envelope)
    second = bus.publish(envelope)
    assert first.stream_id == second.stream_id
    assert second.duplicate
    assert not second.failed
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    assert client.xlen(STREAM_KEY) == 1
    client.close()


def test_competing_consumers_in_one_group_do_not_both_receive_one_entry(redis_url: str) -> None:
    bus = EventBus(redis_url)
    bus.publish(_received())
    bus.publish(_received())
    first = bus.read(ConsumerGroup.INTELLIGENCE_EXTRACTOR, "worker-a", count=1)
    second = bus.read(ConsumerGroup.INTELLIGENCE_EXTRACTOR, "worker-b", count=1)
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].stream_id != second[0].stream_id


def test_pending_redelivery_is_returned_until_ack(redis_url: str) -> None:
    bus = EventBus(redis_url)
    envelope = _received()
    bus.publish(envelope)
    group = ConsumerGroup.API_PROJECTOR
    first = bus.read(group, "projector")
    again = bus.read(group, "projector")
    assert [item.stream_id for item in again] == [item.stream_id for item in first]
    bus.ack(group, first[0])
    assert bus.read(group, "projector") == []


def test_acked_event_id_is_not_delivered_again(redis_url: str) -> None:
    bus = EventBus(redis_url)
    envelope = _received()
    published = bus.publish(envelope)
    group = ConsumerGroup.INTELLIGENCE_EXTRACTOR
    delivered = bus.read(group, "sherlock")
    bus.ack(group, delivered[0])
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    client.xadd(
        STREAM_KEY,
        {ENVELOPE_FIELD: envelope.model_dump_json()},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    client.close()
    assert bus.read(group, "sherlock") == []
    assert published.stream_id != ""


def test_invalid_stream_entry_is_acked_and_skipped(redis_url: str) -> None:
    bus = EventBus(redis_url)
    group = ConsumerGroup.INTELLIGENCE_CORRELATOR
    bus.ensure_group(group)
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    client.xadd(STREAM_KEY, {ENVELOPE_FIELD: "{"}, maxlen=STREAM_MAXLEN, approximate=True)
    assert bus.read(group, "watson") == []
    pending = client.xpending(STREAM_KEY, group.value)
    assert pending["pending"] == 0
    client.close()


def test_publish_failure_is_logged_and_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    envelope = _received()
    bus = EventBus("redis://127.0.0.1:6399/0", socket_timeout_seconds=0.2)
    with caplog.at_level(logging.INFO, logger="switchboard"):
        result = bus.publish(envelope)
    assert result.failed
    assert result.stream_id is None
    assert "event_publish_failed" in caplog.text
    assert "redis_unavailable" in caplog.text
    assert "demo-1" not in caplog.text
    assert "+15551212000" not in caplog.text


def test_api_publisher_uses_the_shared_bus(redis_url: str) -> None:
    from switchboard_api.telephony_events import publish_envelope, telephony_call_received_envelope
    from switchboard_intelligence.deps import event_bus as intelligence_bus
    from switchboard_media.events import event_bus as media_bus

    session_id = uuid4()
    envelope = telephony_call_received_envelope(
        call_session_id=session_id,
        external_call_id="demo-shared",
        carrier="mock",
        caller_number_e164="+15551212000",
        called_number_e164="+15550001001",
        occurred_at=NOW,
    )
    result = publish_envelope(envelope)
    assert result.stream_id
    delivered = intelligence_bus().read(ConsumerGroup.INTELLIGENCE_EXTRACTOR, "sherlock")
    assert len(delivered) == 1
    assert delivered[0].envelope.call_session_id == session_id
    media_published = media_bus().publish(
        build_envelope(
            event_type=EventType.TELEPHONY_CALL_ANSWERED,
            producer=Producer.MEDIA_GATEWAY,
            call_session_id=session_id,
            payload=TelephonyCallAnswered(external_call_id="demo-shared"),
            occurred_at=NOW,
        )
    )
    assert media_published.stream_id
    assert not media_published.failed
