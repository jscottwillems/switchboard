"""Composition root for media-gateway publishes. The socket does not open Postgres."""

from pydantic import ValidationError

from switchboard_events import EventBus, PublishResult
from switchboard_observability import log_info
from switchboard_schemas.events import EventEnvelope

from switchboard_media.settings import get_settings


def event_bus() -> EventBus:
    return EventBus(get_settings().redis_url)


def publish_validated(bus: EventBus, envelope: EventEnvelope) -> PublishResult:
    """Publish one validated envelope. A down Redis leaves the caller up."""

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
