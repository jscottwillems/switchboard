"""Composition root for the extractor, the correlator, and their consumer group.

SB-010 reads `ConsumerGroup.INTELLIGENCE_EXTRACTOR` in
`switchboard_intelligence.extractor_worker` and writes findings.
SB-012 reads `ConsumerGroup.INTELLIGENCE_CORRELATOR` and writes attribution.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from switchboard_events import EventBus
from switchboard_repositories import AttributionWriter, FindingWriter, attribution_writer, finding_writer

from switchboard_intelligence.settings import get_settings


def event_bus() -> EventBus:
    return EventBus(get_settings().redis_url)


@contextmanager
def open_finding_writer() -> Iterator[FindingWriter]:
    with finding_writer(get_settings().database_url) as writer:
        yield writer


@contextmanager
def open_attribution_writer() -> Iterator[AttributionWriter]:
    with attribution_writer(get_settings().database_url) as writer:
        yield writer
