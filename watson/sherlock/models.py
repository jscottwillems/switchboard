"""Indicators WATSON consumes. This is not SHERLOCK's service schema.

The kinds below are the fields WATSON knows how to score. When SHERLOCK's
observation schema lands, adapt it onto these models rather than folding
extraction into the scorer.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ObservationKind(str, Enum):
    """Typed indicator categories. Confidence is required on every observation."""

    CLAIMED_ORGANIZATION = "claimed_organization"
    CALLBACK_IDENTIFIER = "callback_identifier"
    DOMAIN = "domain"
    EMAIL_PATTERN = "email_pattern"
    REPEATED_PHRASE = "repeated_phrase"
    OPENING_SCRIPT = "opening_script"
    IVR_STRUCTURE = "ivr_structure"


class IntelligenceObservation(BaseModel):
    """One structured indicator with a confidence in [0, 1]."""

    model_config = ConfigDict(extra="forbid")

    kind: ObservationKind
    value: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence: str | None = None


class CallIntelligence(BaseModel):
    """All indicators SHERLOCK (or a fixture) attached to one completed call."""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(min_length=1)
    observations: list[IntelligenceObservation]
