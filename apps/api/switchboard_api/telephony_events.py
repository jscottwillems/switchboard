"""Publish telephony envelopes through the shared event bus.

The voice webhook calls `publish_envelope` after the session commit. The stream
entry stays one `envelope` JSON field on `switchboard.events`, approximate
maxlen 100000. Redis errors are logged inside `EventBus.publish` and do not
propagate, so a committed session is left in place (ADR-011).
"""

from datetime import datetime
from uuid import UUID

from switchboard_events import STREAM_KEY, EventBus, PublishResult, build_envelope
from switchboard_schemas.enums import EventType, Producer
from switchboard_schemas.events import EventEnvelope, TelephonyCallReceived

from switchboard_api.settings import get_settings

EVENT_STREAM_KEY = STREAM_KEY


def event_bus() -> EventBus:
    return EventBus(get_settings().redis_url)


def telephony_call_received_envelope(
    *,
    call_session_id: UUID,
    external_call_id: str,
    carrier: str,
    caller_number_e164: str,
    called_number_e164: str,
    occurred_at: datetime,
) -> EventEnvelope:
    return build_envelope(
        event_type=EventType.TELEPHONY_CALL_RECEIVED,
        producer=Producer.API,
        call_session_id=call_session_id,
        payload=TelephonyCallReceived(
            external_call_id=external_call_id,
            carrier=carrier,
            caller_number_e164=caller_number_e164,
            called_number_e164=called_number_e164,
        ),
        occurred_at=occurred_at,
    )


def publish_envelope(envelope: EventEnvelope) -> PublishResult:
    """Validate and publish. Redis failure returns `failed=True` and does not raise."""

    return event_bus().publish(envelope)
