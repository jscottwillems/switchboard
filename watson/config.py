"""Explicit weights and thresholds for the deterministic scorer.

Tier A anchors carry the association score. Tier B is script and narrative.
Tier C (timing, duration, ivr_prompts) is retrieval and tie-break only:
its group weight on association_score is 0. Missing evidence contributes 0.
Weights are not renormalized. Embeddings are not used.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from watson.models import LEAF_FEATURES

ANCHOR_FEATURES = (
    "phone_e164",
    "case_id",
    "domain_registrable",
    "email_domain_registrable",
    "claimed_company_normalized",
)
SCRIPT_FEATURES = (
    "opening_script_text",
    "opening_script_fingerprint",
    "script_phrase_normalized",
    "pretext_category_canonical",
    "transfer_destination_claimed",
    "script_language",
)
STRUCTURE_FEATURES = ("timing", "duration", "ivr_prompts")


def _weights_sum_to_one(weights: dict[str, float], label: str) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"{label} weights sum to {total}, expected 1")


class ScoringConfig(BaseModel):
    """Operating point for retrieval, scoring, and the associate-or-new decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "phone_e164": 0.28,
            "case_id": 0.16,
            "domain_registrable": 0.22,
            "email_domain_registrable": 0.16,
            "claimed_company_normalized": 0.18,
        }
    )
    script_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "opening_script_text": 0.32,
            "opening_script_fingerprint": 0.22,
            "script_phrase_normalized": 0.20,
            "pretext_category_canonical": 0.12,
            "transfer_destination_claimed": 0.10,
            "script_language": 0.04,
        }
    )
    structure_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "timing": 0.50,
            "duration": 0.20,
            "ivr_prompts": 0.30,
        }
    )
    group_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "anchor": 0.60,
            "script": 0.40,
            "structure": 0.00,
        }
    )
    associate_threshold: float = Field(default=0.50, ge=0, le=1)
    # Anchor mass that may associate without a strong script.
    min_anchor_group: float = Field(default=0.34, ge=0, le=1)
    # Near-copy script that may pass the guard. The 0.40 script weight still
    # keeps script-only scores under associate_threshold.
    min_script_group: float = Field(default=0.85, ge=0, le=1)
    min_observation_confidence: float = Field(default=0.50, ge=0, le=1)
    opening_word_count: int = Field(default=70, ge=1)
    opening_retrieval_jaccard: float = Field(default=0.08, ge=0, le=1)
    transcript_retrieval_jaccard: float = Field(default=0.08, ge=0, le=1)
    timing_retrieval_seconds: float = Field(default=900, ge=0)
    reason_feature_cutoff: float = Field(default=0.20, ge=0, le=1)
    edit_bucket_high: float = Field(default=0.90, ge=0, le=1)
    edit_bucket_mid: float = Field(default=0.80, ge=0, le=1)
    email_domain_score: float = Field(default=0.70, ge=0, le=1)
    # Shared English is not campaign evidence.
    nondistinctive_script_language: str = "en"

    @model_validator(mode="after")
    def _weights_cover_features(self) -> "ScoringConfig":
        groups = {
            "anchor": (self.anchor_weights, ANCHOR_FEATURES),
            "script": (self.script_weights, SCRIPT_FEATURES),
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
        if tuple(self.group_weights) != ("anchor", "script", "structure"):
            raise ValueError("group weight keys must be anchor, script, structure")
        if self.edit_bucket_mid > self.edit_bucket_high:
            raise ValueError("edit_bucket_mid cannot exceed edit_bucket_high")
        if self.group_weights["structure"] != 0:
            raise ValueError("structure weight must stay 0; tier C is tie-break only")
        return self
