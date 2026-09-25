"""Explicit weights and thresholds for the deterministic scorer.

Missing evidence contributes 0. Weights are not renormalized, so a single
weak feature cannot fill the score. Embeddings are not used.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from watson.models import LEAF_FEATURES

SCRIPT_FEATURES = ("opening_script", "transcript", "repeated_phrases")
IDENTIFIER_FEATURES = (
    "claimed_organization",
    "callback_identifiers",
    "domains",
    "email_patterns",
)
STRUCTURE_FEATURES = ("timing", "duration", "transfer_behavior", "ivr_structure")


def _weights_sum_to_one(weights: dict[str, float], label: str) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{label} weights sum to {total}, expected 1")


class ScoringConfig(BaseModel):
    """Operating point for retrieval, scoring, and the associate-or-new decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    script_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "opening_script": 0.45,
            "transcript": 0.35,
            "repeated_phrases": 0.20,
        }
    )
    identifier_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "claimed_organization": 0.34,
            "callback_identifiers": 0.30,
            "domains": 0.20,
            "email_patterns": 0.16,
        }
    )
    structure_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "timing": 0.35,
            "duration": 0.20,
            "transfer_behavior": 0.20,
            "ivr_structure": 0.25,
        }
    )
    group_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "script": 0.70,
            "identifier": 0.25,
            "structure": 0.05,
        }
    )
    associate_threshold: float = Field(default=0.50, ge=0, le=1)
    # Near-copy scripts may associate without shared identifiers.
    # Partial boilerplate stays under this group score on the synthetic set.
    min_script_group: float = Field(default=0.40, ge=0, le=1)
    # A thinner script can still associate when several identifiers agree.
    min_script_with_identifiers: float = Field(default=0.25, ge=0, le=1)
    min_identifier_group: float = Field(default=0.50, ge=0, le=1)
    min_observation_confidence: float = Field(default=0.50, ge=0, le=1)
    opening_word_count: int = Field(default=70, ge=1)
    opening_retrieval_jaccard: float = Field(default=0.08, ge=0, le=1)
    transcript_retrieval_jaccard: float = Field(default=0.08, ge=0, le=1)
    timing_retrieval_seconds: float = Field(default=900, ge=0)
    # Leaf scores at or above this cutoff are spelled out in reasons.
    reason_feature_cutoff: float = Field(default=0.20, ge=0, le=1)
    # Near-copy edit-distance buckets. Looser structural similarity is ignored.
    edit_bucket_high: float = Field(default=0.90, ge=0, le=1)
    edit_bucket_mid: float = Field(default=0.80, ge=0, le=1)
    email_domain_score: float = Field(default=0.70, ge=0, le=1)

    @model_validator(mode="after")
    def _weights_cover_features(self) -> "ScoringConfig":
        groups = {
            "script": (self.script_weights, SCRIPT_FEATURES),
            "identifier": (self.identifier_weights, IDENTIFIER_FEATURES),
            "structure": (self.structure_weights, STRUCTURE_FEATURES),
        }
        seen: list[str] = []
        for label, (weights, expected) in groups.items():
            if tuple(weights) != expected:
                raise ValueError(f"{label} weight keys must be {expected}")
            _weights_sum_to_one(weights, label)
            seen.extend(weights)
        if set(seen) != set(LEAF_FEATURES) or len(seen) != len(LEAF_FEATURES):
            raise ValueError("feature weights must partition the leaf features")
        _weights_sum_to_one(self.group_weights, "group")
        if tuple(self.group_weights) != ("script", "identifier", "structure"):
            raise ValueError("group weight keys must be script, identifier, structure")
        if self.edit_bucket_mid > self.edit_bucket_high:
            raise ValueError("edit_bucket_mid cannot exceed edit_bucket_high")
        if self.min_script_with_identifiers > self.min_script_group:
            raise ValueError("min_script_with_identifiers cannot exceed min_script_group")
        return self
