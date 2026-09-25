"""Call records, feature vectors, and campaign association results."""

from datetime import datetime
from enum import Enum
from typing import Never

from pydantic import BaseModel, ConfigDict, Field, model_validator

LEAF_FEATURES: tuple[str, ...] = (
    "opening_script",
    "transcript",
    "repeated_phrases",
    "claimed_organization",
    "callback_identifiers",
    "domains",
    "email_patterns",
    "timing",
    "duration",
    "transfer_behavior",
    "ivr_structure",
)


class DecisionAction(str, Enum):
    """Whether a completed call joins an existing campaign or opens one."""

    NEW_CAMPAIGN = "new_campaign"
    ASSOCIATE = "associate"


def assert_never(value: Never) -> Never:
    """Fail closed when a union or enum gains a variant that is not handled."""
    raise RuntimeError(f"Unhandled variant: {value!r}")


class CompletedCall(BaseModel):
    """A finished honeypot call. Identifier extraction belongs to SHERLOCK."""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime
    caller_id: str | None = None
    transcript: str
    transferred: bool = False
    ivr_path: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ended_after_start(self) -> "CompletedCall":
        if self.ended_at < self.started_at:
            raise ValueError("ended_at is earlier than started_at")
        return self

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


class CallFeatures(BaseModel):
    """Deterministic features WATSON scores. Caller id is intentionally absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float = Field(ge=0)
    opening_text: str
    opening_tokens: frozenset[str]
    transcript_tokens: frozenset[str]
    repeated_phrases: frozenset[str]
    claimed_organizations: frozenset[str]
    callback_identifiers: frozenset[str]
    domains: frozenset[str]
    email_patterns: frozenset[str]
    transferred: bool
    ivr_path: tuple[str, ...]


class ScoreBreakdown(BaseModel):
    """Similarity of one call against one other call or campaign member."""

    model_config = ConfigDict(extra="forbid")

    association_score: float = Field(ge=0, le=1)
    feature_scores: dict[str, float]
    feature_reasons: list[str]
    matched_call_id: str | None = None
    campaign_id: str | None = None

    @model_validator(mode="after")
    def _scores_in_unit_interval(self) -> "ScoreBreakdown":
        missing = [name for name in LEAF_FEATURES if name not in self.feature_scores]
        if missing:
            raise ValueError(f"feature_scores missing {missing}")
        extra = [name for name in self.feature_scores if name not in LEAF_FEATURES]
        if extra:
            raise ValueError(f"feature_scores has unknown keys {extra}")
        for name, value in self.feature_scores.items():
            if value < 0 or value > 1:
                raise ValueError(f"{name} score {value} is outside [0, 1]")
        return self


class CampaignAssociation(BaseModel):
    """Explainable link from a completed call to a campaign."""

    model_config = ConfigDict(extra="forbid")

    call_id: str
    campaign_id: str
    association_score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(min_length=1)
    feature_scores: dict[str, float]
    decision: DecisionAction
    # Closest compared call. Set on associate, and on new_campaign when a
    # candidate was scored and rejected. Absent when the store was empty.
    matched_call_id: str | None = None
    threshold: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _feature_scores_bounded(self) -> "CampaignAssociation":
        missing = [name for name in LEAF_FEATURES if name not in self.feature_scores]
        if missing:
            raise ValueError(f"feature_scores missing {missing}")
        for name, value in self.feature_scores.items():
            if name not in LEAF_FEATURES:
                raise ValueError(f"unknown feature {name}")
            if value < 0 or value > 1:
                raise ValueError(f"{name} score {value} is outside [0, 1]")
        if self.decision is DecisionAction.ASSOCIATE and self.matched_call_id is None:
            raise ValueError("associate decisions require matched_call_id")
        return self
