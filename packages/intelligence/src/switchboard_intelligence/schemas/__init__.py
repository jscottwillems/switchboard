"""Canonical Sherlock schemas. Pydantic models are the source of truth."""

from switchboard_intelligence.schemas.attribution import (
    Attribution,
    AttributionStatus,
    AttributionSubject,
)
from switchboard_intelligence.schemas.bundle import IntelligenceBundle
from switchboard_intelligence.schemas.campaign import AssociationReason, CampaignAssociation
from switchboard_intelligence.schemas.common import SCHEMA_VERSION
from switchboard_intelligence.schemas.hints import ElicitedHint
from switchboard_intelligence.schemas.inference import (
    IdentifierKind,
    Inference,
    InferenceKind,
    InferenceMethod,
    PhoneSourceTag,
)
from switchboard_intelligence.schemas.observation import (
    Observation,
    ObservationKind,
    PaymentMethod,
    PretextCategory,
    ScriptLocale,
)
from switchboard_intelligence.schemas.transcript import SpeakerRole, Transcript, TranscriptSegment

__all__ = [
    "SCHEMA_VERSION",
    "AssociationReason",
    "Attribution",
    "AttributionStatus",
    "AttributionSubject",
    "CampaignAssociation",
    "ElicitedHint",
    "IdentifierKind",
    "Inference",
    "InferenceKind",
    "InferenceMethod",
    "IntelligenceBundle",
    "Observation",
    "ObservationKind",
    "PaymentMethod",
    "PhoneSourceTag",
    "PretextCategory",
    "ScriptLocale",
    "SpeakerRole",
    "Transcript",
    "TranscriptSegment",
]
