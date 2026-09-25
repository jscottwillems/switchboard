"""Bundle returned for one call."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from switchboard_intelligence.schemas.attribution import Attribution
from switchboard_intelligence.schemas.common import SCHEMA_VERSION
from switchboard_intelligence.schemas.inference import Inference
from switchboard_intelligence.schemas.observation import Observation


class IntelligenceBundle(BaseModel):
    """Observations, inferences, and attributions for a single call."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sherlock.intelligence.v1"] = SCHEMA_VERSION
    call_id: str = Field(min_length=1)
    observations: list[Observation]
    inferences: list[Inference]
    attributions: list[Attribution]

    @model_validator(mode="after")
    def call_ids_match(self) -> "IntelligenceBundle":
        for observation in self.observations:
            if observation.call_id != self.call_id:
                raise ValueError("observation call_id does not match the bundle")
        for inference in self.inferences:
            if inference.call_id != self.call_id:
                raise ValueError("inference call_id does not match the bundle")
        for attribution in self.attributions:
            if attribution.call_id != self.call_id:
                raise ValueError("attribution call_id does not match the bundle")
        return self
