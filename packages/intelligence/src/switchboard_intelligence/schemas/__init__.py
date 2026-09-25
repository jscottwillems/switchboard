"""Canonical Sherlock schemas. Pydantic models are the source of truth."""

from switchboard_intelligence.schemas.attribution import (
    Attribution,
    AttributionStatus,
    AttributionSubject,
)
from switchboard_intelligence.schemas.bundle import IntelligenceBundle
from switchboard_intelligence.schemas.common import SCHEMA_VERSION
from switchboard_intelligence.schemas.hints import ElicitedHint
from switchboard_intelligence.schemas.inference import Inference, InferenceKind, InferenceMethod
from switchboard_intelligence.schemas.observation import (
    Observation,
    ObservationKind,
    PaymentMethod,
    PretextCategory,
)
from switchboard_intelligence.schemas.transcript import SpeakerRole, Transcript, TranscriptSegment

__all__ = [
    "SCHEMA_VERSION",
    "Attribution",
    "AttributionStatus",
    "AttributionSubject",
    "ElicitedHint",
    "Inference",
    "InferenceKind",
    "InferenceMethod",
    "IntelligenceBundle",
    "Observation",
    "ObservationKind",
    "PaymentMethod",
    "PretextCategory",
    "SpeakerRole",
    "Transcript",
    "TranscriptSegment",
]
