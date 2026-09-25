"""Composition root for repositories and the event bus.

SB-003 publishes through `telephony_events`. Call reads use `open_read_models`.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from switchboard_events import EventBus
from switchboard_repositories import (
    ObservationWriter,
    ReadModels,
    observation_writer,
    read_models,
)

from switchboard_api.settings import get_settings
from switchboard_api.telephony_events import event_bus


def get_event_bus() -> EventBus:
    return event_bus()


@contextmanager
def open_observation_writer() -> Iterator[ObservationWriter]:
    with observation_writer(get_settings().database_url) as writer:
        yield writer


@contextmanager
def open_read_models() -> Iterator[ReadModels]:
    with read_models(get_settings().database_url) as models:
        yield models
