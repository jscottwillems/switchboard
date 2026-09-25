"""Attributions: links from intelligence to an actor, campaign, or kit.

This milestone defines the record. It does not ship a campaign corpus,
so extraction returns an empty attribution list.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from switchboard_intelligence.schemas.common import SCHEMA_VERSION, Confidence


class AttributionSubject(str, Enum):
    CAMPAIGN = "campaign"
    ACTOR = "actor"
    INFRASTRUCTURE = "infrastructure"
    SCRIPT_FAMILY = "script_family"
    UNKNOWN = "unknown"


class AttributionStatus(str, Enum):
    HYPOTHESIZED = "hypothesized"
    SUPPORTED = "supported"
    CONFIRMED = "confirmed"


class Attribution(BaseModel):
    """A hypothesized link to an external subject.

    Distinct from Observation (no transcript span) and from Inference
    (the subject is an actor, campaign, or kit rather than a proposition
    about this call alone).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sherlock.intelligence.v1"] = SCHEMA_VERSION
    record_type: Literal["attribution"] = "attribution"
    attribution_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    subject_type: AttributionSubject
    subject_key: str = Field(min_length=1)
    subject_label: str = Field(min_length=1)
    supporting_observation_ids: list[str] = Field(default_factory=list)
    supporting_inference_ids: list[str] = Field(default_factory=list)
    confidence: Confidence
    status: AttributionStatus
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def has_support(self) -> "Attribution":
        if not self.supporting_observation_ids and not self.supporting_inference_ids:
            raise ValueError("attribution requires an observation id or an inference id")
        return self
