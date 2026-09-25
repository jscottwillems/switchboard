"""Sherlock intelligence: observations, inferences, and attributions."""

from switchboard_intelligence.extraction.pipeline import extract_intelligence
from switchboard_intelligence.schemas import (
    SCHEMA_VERSION,
    Attribution,
    AttributionStatus,
    AttributionSubject,
    ElicitedHint,
    Inference,
    InferenceKind,
    InferenceMethod,
    IntelligenceBundle,
    Observation,
    ObservationKind,
    PaymentMethod,
    PretextCategory,
    SpeakerRole,
    Transcript,
    TranscriptSegment,
)

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
    "extract_intelligence",
]
