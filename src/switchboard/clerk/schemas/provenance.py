"""Fact classes and epistemic layers for evidence.

Reported caller metadata, spoken identifiers, raw observations, confirmed
observations, derived interpretations, and campaign attribution stay on
separate tags. CLERK copies those tags from inputs and does not recompute them.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, assert_never

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict

PROVISIONAL_UPSTREAM_SCHEMA_ID: Literal["clerk.provisional_upstream.v0"] = (
    "clerk.provisional_upstream.v0"
)
SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
ABSENT = "None in source package."
SYNTHETIC_BANNER = (
    "SYNTHETIC FIXTURE. Values in this report are copied from labeled synthetic inputs."
)
UNMARKED_BANNER = (
    "Source package is marked synthetic=false. Values in this report are copied from the package."
)


class ClerkModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def require_text(value: str) -> str:
    if value.strip() == "":
        raise ValueError("text must not be empty")
    return value


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def require_unit_interval(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("score must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError("score must be a finite number from 0 to 1")
    return number


NonEmptyStr = Annotated[str, AfterValidator(require_text)]
AwareDatetime = Annotated[datetime, AfterValidator(require_aware)]
UnitScore = Annotated[float, BeforeValidator(require_unit_interval)]


class FactClass(str, Enum):
    REPORTED_CALLER_METADATA = "reported_caller_metadata"
    SPOKEN_IDENTIFIER = "spoken_identifier"
    RAW_OBSERVATION = "raw_observation"
    CONFIRMED_OBSERVATION = "confirmed_observation"
    DERIVED_INTERPRETATION = "derived_interpretation"
    DERIVED_ASSOCIATION = "derived_association"


class EpistemicLayer(str, Enum):
    RAW_OBSERVATION = "raw_observation"
    DERIVED_INTERPRETATION = "derived_interpretation"
    CAMPAIGN_ATTRIBUTION = "campaign_attribution"


class PackageScope(str, Enum):
    SINGLE_CALL = "single_call"
    CAMPAIGN = "campaign"
    TECHNICAL_INCIDENT = "technical_incident"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(ClerkModel):
    """Confidence copied from a source record.

    CLERK stores the supplied level, score, and basis. It does not derive the
    level from the score.
    """

    level: ConfidenceLevel
    score: UnitScore
    basis: NonEmptyStr


class SupportingTimestamp(ClerkModel):
    source_id: NonEmptyStr
    label: NonEmptyStr
    at: AwareDatetime
    call_id: NonEmptyStr | None = None
    excerpt_id: NonEmptyStr | None = None
    artifact_id: NonEmptyStr | None = None


def legend_definition(fact_class: FactClass) -> tuple[EpistemicLayer, str]:
    """Glossary text for a fact class. The text does not describe a call."""

    match fact_class:
        case FactClass.REPORTED_CALLER_METADATA:
            return (
                EpistemicLayer.RAW_OBSERVATION,
                "Displayed signaling or caller-ID values copied from the call record.",
            )
        case FactClass.SPOKEN_IDENTIFIER:
            return (
                EpistemicLayer.RAW_OBSERVATION,
                "Identifier values copied from supplied transcript excerpts.",
            )
        case FactClass.RAW_OBSERVATION:
            return (
                EpistemicLayer.RAW_OBSERVATION,
                "Source material, or an observation supplied without confirmation.",
            )
        case FactClass.CONFIRMED_OBSERVATION:
            return (
                EpistemicLayer.RAW_OBSERVATION,
                "Observation supplied with confirmation. This tag stays on the observation.",
            )
        case FactClass.DERIVED_INTERPRETATION:
            return (
                EpistemicLayer.DERIVED_INTERPRETATION,
                "Interpretation supplied as derived.",
            )
        case FactClass.DERIVED_ASSOCIATION:
            return (
                EpistemicLayer.CAMPAIGN_ATTRIBUTION,
                "Campaign link or association reason supplied as attribution.",
            )
        case _ as unreachable:
            assert_never(unreachable)


def locked_pair(fact_class: FactClass, epistemic: EpistemicLayer) -> None:
    expected, _definition = legend_definition(fact_class)
    if epistemic != expected:
        raise ValueError(f"{fact_class.value} belongs on epistemic layer {expected.value}")
