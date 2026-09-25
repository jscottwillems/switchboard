"""Inferences: judgments supported by observations, not transcript spans."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from switchboard_intelligence.schemas.common import SCHEMA_VERSION, Confidence


class InferenceKind(str, Enum):
    IMPERSONATED_ORGANIZATION = "impersonated_organization"
    PAYMENT_RAIL = "payment_rail"
    DATA_TARGET = "data_target"
    PRESSURE_TACTIC = "pressure_tactic"
    OFFER_TERMS = "offer_terms"
    CALLBACK_CHANNEL = "callback_channel"
    THREATENED_CONSEQUENCE = "threatened_consequence"
    OTHER = "other"


class InferenceMethod(str, Enum):
    RULE = "rule"
    MODEL = "model"
    ANALYST = "analyst"


class Inference(BaseModel):
    """A proposition derived from one or more observations.

    Inferences have no transcript span. The evidence is
    `supporting_observation_ids`.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sherlock.intelligence.v1"] = SCHEMA_VERSION
    record_type: Literal["inference"] = "inference"
    inference_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    kind: InferenceKind
    proposition: str = Field(min_length=1)
    supporting_observation_ids: list[str] = Field(min_length=1)
    confidence: Confidence
    method: InferenceMethod
    rationale: str = Field(min_length=1)
