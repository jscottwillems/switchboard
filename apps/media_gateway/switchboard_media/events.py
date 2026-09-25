"""Composition root for media-gateway publishes. The socket does not open Postgres."""

from switchboard_events import EventBus

from switchboard_media.settings import get_settings


def event_bus() -> EventBus:
    return EventBus(get_settings().redis_url)
