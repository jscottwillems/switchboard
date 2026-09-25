"""Durable consumer groups from docs/EVENTS.md."""

from enum import StrEnum


class ConsumerGroup(StrEnum):
    """One group per writer. Each group receives every stream entry."""

    API_PROJECTOR = "api.projector"
    INTELLIGENCE_EXTRACTOR = "intelligence.extractor"
    INTELLIGENCE_CORRELATOR = "intelligence.correlator"
