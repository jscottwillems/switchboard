"""Best-effort publish of telephony.call.received.

SB-016 owns the shared Redis helper and consumer groups. Until that lands,
the voice webhook validates an EventEnvelope and XADDs it to switchboard.events.
A publish failure is logged and does not roll back the session (ADR-011).
"""

from datetime import datetime
from uuid import UUID, uuid4

import redis
from redis.exceptions import RedisError

from switchboard_observability import log_info
from switchboard_schemas.enums import EventType, Producer
from switchboard_schemas.events import EventEnvelope, TelephonyCallReceived, validate_event

from switchboard_api.settings import get_settings

EVENT_STREAM_KEY = "switchboard.events"
_STREAM_MAXLEN = 100_000


def telephony_call_received_envelope(
    *,
    call_session_id: UUID,
    external_call_id: str,
    carrier: str,
    caller_number_e164: str,
    called_number_e164: str,
    occurred_at: datetime,
) -> EventEnvelope:
    payload = TelephonyCallReceived(
        external_call_id=external_call_id,
        carrier=carrier,
        caller_number_e164=caller_number_e164,
        called_number_e164=called_number_e164,
    )
    return EventEnvelope(
        event_id=uuid4(),
        event_type=EventType.TELEPHONY_CALL_RECEIVED,
        event_version=1,
        occurred_at=occurred_at,
        producer=Producer.API,
        call_session_id=call_session_id,
        payload=payload.model_dump(mode="json"),
    )


def publish_envelope(envelope: EventEnvelope) -> None:
    validate_event(envelope)
    client = redis.Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
    try:
        client.xadd(
            EVENT_STREAM_KEY,
            {"envelope": envelope.model_dump_json()},
            maxlen=_STREAM_MAXLEN,
            approximate=True,
        )
    except (RedisError, OSError):
        log_info(
            "event_publish_failed",
            event_type=envelope.event_type.value,
            call_session_id=str(envelope.call_session_id),
            reason="redis_unavailable",
        )
    finally:
        client.close()
