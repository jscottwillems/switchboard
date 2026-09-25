"""Thin Sherlock adapter: correlation observations, inference, and a fixture provider."""

from watson.sherlock.interface import CallIntelligenceProvider
from watson.sherlock.mock import FixtureIntelligenceProvider
from watson.sherlock.models import (
    SCHEMA_VERSION,
    CallIntelligence,
    CorrelationInference,
    EmailSplit,
    Observation,
    ObservationKind,
    PhoneE164,
)

__all__ = [
    "SCHEMA_VERSION",
    "CallIntelligence",
    "CallIntelligenceProvider",
    "CorrelationInference",
    "EmailSplit",
    "FixtureIntelligenceProvider",
    "Observation",
    "ObservationKind",
    "PhoneE164",
]
