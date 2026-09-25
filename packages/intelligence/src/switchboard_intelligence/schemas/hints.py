"""Optional Loki breadcrumbs. These are not observations."""

from pydantic import BaseModel, ConfigDict, Field

from switchboard_intelligence.schemas.observation import ObservationKind


class ElicitedHint(BaseModel):
    """Untyped, unverified breadcrumb from Loki.

    `goal` is an ObservationKind value so Loki's `goals_completed` and
    `goals_remaining` strings match Sherlock's field names. The hint has no
    confidence, no transcript span, and is not an Observation. Sherlock does
    not promote hints into observations.
    """

    model_config = ConfigDict(extra="forbid")

    goal: ObservationKind
    surface_text: str = Field(min_length=1)
    turn_index: int = Field(ge=0)
