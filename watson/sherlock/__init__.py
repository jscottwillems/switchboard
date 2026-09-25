"""Thin SHERLOCK adapter: protocol, typed observations, and a fixture provider."""

from watson.sherlock.interface import CallIntelligenceProvider
from watson.sherlock.mock import FixtureIntelligenceProvider
from watson.sherlock.models import (
    CallIntelligence,
    IntelligenceObservation,
    ObservationKind,
)

__all__ = [
    "CallIntelligence",
    "CallIntelligenceProvider",
    "FixtureIntelligenceProvider",
    "IntelligenceObservation",
    "ObservationKind",
]
