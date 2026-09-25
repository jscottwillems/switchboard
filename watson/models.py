"""Call records, feature vectors, and campaign association results."""

from datetime import datetime
from enum import Enum
from typing import Never

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Feature-score keys are the correlation field names WATSON cites in reasons.
# timing and duration come from the call store. The rest are Observation or
# Inference fields. Tier C does not add into association_score.
LEAF_FEATURES: tuple[str, ...] = (
    "phone_e164",
    "case_id",
    "domain_registrable",
    "email_domain_registrable",
    "claimed_company_normalized",
    "opening_script_text",
    "opening_script_fingerprint",
    "script_phrase_normalized",
    "pretext_category_canonical",
    "transfer_destination_claimed",
    "script_language",
    "timing",
    "duration",
    "ivr_prompts",
)


class DecisionAction(str, Enum):
    """Whether a completed call joins an existing campaign or opens one."""

    NEW_CAMPAIGN = "new_campaign"
    ASSOCIATE = "associate"


def assert_never(value: Never) -> Never:
    """Fail closed when a union or enum gains a variant that is not handled."""
    raise RuntimeError(f"Unhandled variant: {value!r}")


class CompletedCall(BaseModel):
    """Call-store record. CLI/ANI, timing, and duration are not Observations."""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(min_length=1)
    started_at: datetime
    ended_at: datetime
    # CLI/ANI from the call store. Not an association anchor.
    caller_id: str | None = None
    transcript: str

    @model_validator(mode="after")
    def _ended_after_start(self) -> "CompletedCall":
        if self.ended_at < self.started_at:
            raise ValueError("ended_at is earlier than started_at")
        return self

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


class CallFeatures(BaseModel):
    """Scoreable view of one call. CLI/ANI is not stored here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float = Field(ge=0)
    phone_e164: tuple[tuple[str, str], ...]
    case_id: frozenset[str]
    domain_registrable: frozenset[str]
    email_split: tuple[tuple[str, str, str], ...]
    claimed_company_normalized: frozenset[str]
    calling_from: frozenset[str]
    opening_script_text: str
    opening_tokens: frozenset[str]
    opening_turns: tuple[str, ...]
    transcript_tokens: frozenset[str]
    opening_script_fingerprint: str | None
    script_phrase_normalized: frozenset[str]
    pretext_category_canonical: str | None
    transfer_destination_claimed: frozenset[str]
    script_language: str | None
    ivr_prompts: tuple[str, ...]


class ScoreBreakdown(BaseModel):
    """Similarity of one call against one other call or campaign member."""

    model_config = ConfigDict(extra="forbid")

    association_score: float = Field(ge=0, le=1)
    feature_scores: dict[str, float]
    feature_reasons: list[str]
    matched_call_id: str | None = None
    campaign_id: str | None = None
    tier_c_score: float = Field(default=0.0, ge=0, le=1)

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
