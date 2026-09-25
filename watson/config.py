"""Evidence weights for the deterministic scorer.

Contributions are absolute: a leaf score of 1 adds that weight to the total.
The total is capped at 1. Missing evidence adds 0. Weights are not
renormalized when a finding kind is absent.

`callback_number` is large enough that a shared E.164 alone clears the
associate threshold. That is the only kind Sherlock emits today. The other
FindingKind weights stay below the threshold individually so one future kind
cannot merge calls by itself. Tier C (timing, duration) does not add into
association_score. Embeddings are not used.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from watson.models import LEAF_FEATURES

ANCHOR_FEATURES = (
    "callback_number",
    "organization_name",
    "url",
    "payment_method",
    "other",
)
SCRIPT_FEATURES = ("pretext", "person_name")
CALL_STORE_FEATURES = ("transcript_overlap",)
STRUCTURE_FEATURES = ("timing", "duration")
EVIDENCE_FEATURES = ANCHOR_FEATURES + SCRIPT_FEATURES + CALL_STORE_FEATURES


def _weights_sum_to_one(weights: dict[str, float], label: str) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{label} weights sum to {total}, expected 1")


class ScoringConfig(BaseModel):
    """Operating point for retrieval, scoring, and the associate-or-new decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "callback_number": 0.72,
            "organization_name": 0.20,
            "url": 0.16,
            "payment_method": 0.10,
            "other": 0.14,
            "pretext": 0.18,
            "person_name": 0.06,
            "transcript_overlap": 0.12,
        }
    )
    structure_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "timing": 0.60,
            "duration": 0.40,
        }
    )
    associate_threshold: float = Field(default=0.50, ge=0, le=1)
    # Anchor evidence that may associate. Callback alone is 0.72.
    min_anchor_group: float = Field(default=0.50, ge=0, le=1)
    min_observation_confidence: float = Field(default=0.50, ge=0, le=1)
    opening_word_count: int = Field(default=70, ge=1)
    opening_retrieval_jaccard: float = Field(default=0.08, ge=0, le=1)
    transcript_retrieval_jaccard: float = Field(default=0.08, ge=0, le=1)
    timing_retrieval_seconds: float = Field(default=900, ge=0)
    reason_feature_cutoff: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def _weights_cover_features(self) -> "ScoringConfig":
        if tuple(self.evidence_weights) != EVIDENCE_FEATURES:
            raise ValueError(f"evidence weight keys must be {EVIDENCE_FEATURES}")
        if tuple(self.structure_weights) != STRUCTURE_FEATURES:
            raise ValueError(f"structure weight keys must be {STRUCTURE_FEATURES}")
        _weights_sum_to_one(self.structure_weights, "structure")
        covered = set(self.evidence_weights) | set(self.structure_weights)
        if covered != set(LEAF_FEATURES):
            raise ValueError("weights must cover the leaf features")
        for name, weight in self.evidence_weights.items():
            if weight < 0 or weight > 1:
                raise ValueError(f"{name} weight {weight} is outside [0, 1]")
        if self.evidence_weights["callback_number"] < 0.50:
            raise ValueError("callback_number weight must be at least 0.50")
        for name, weight in self.evidence_weights.items():
            if name != "callback_number" and weight >= 0.50:
                raise ValueError(f"{name} alone must stay under 0.50")
        return self
