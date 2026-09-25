"""Measure the deterministic scorer against labeled synthetic calls."""

from dataclasses import dataclass

from watson.config import ScoringConfig
from watson.dataset import RunnableDataset, SyntheticDataset, prepare
from watson.decision import evidence_guard_passes
from watson.features import extract_features
from watson.models import LEAF_FEATURES, CallFeatures, CampaignAssociation, DecisionAction
from watson.pipeline import AssociationPipeline
from watson.scoring import combine_association_score, score_features

# Score-only cutoffs reported alongside the operating threshold.
REPORT_THRESHOLDS: tuple[float, ...] = (0.30, 0.40, 0.50, 0.60, 0.70)

SCENARIO_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("clearly_related_irs", "irs-1", "irs-2"),
    ("changing_identifiers_irs", "irs-1", "irs-4"),
    ("repeat_caller_different_campaign", "irs-4", "tech-3"),
    ("partial_irs_bank", "irs-1", "bank-1"),
    ("partial_solar_insurance", "solar-1", "insurance-1"),
    ("unrelated_gift_survey", "gift-1", "survey-1"),
    ("clearly_related_warranty", "warranty-1", "warranty-2"),
)


@dataclass(frozen=True)
class PairwiseCounts:
    """Pair classification at one decision rule."""

    label: str
    threshold: float
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    guard_applied: bool

    @property
    def precision(self) -> float:
        predicted = self.true_positive + self.false_positive
        if predicted == 0:
            return 1.0
        return self.true_positive / predicted

    @property
    def recall(self) -> float:
        actual = self.true_positive + self.false_negative
        if actual == 0:
            return 1.0
        return self.true_positive / actual


@dataclass(frozen=True)
class IngestRow:
    call_id: str
    ground_truth_campaign_id: str
    campaign_id: str
    decision: DecisionAction
    association_score: float
    matched_call_id: str | None


@dataclass(frozen=True)
class EvaluationReport:
    """Scorer gap, threshold table, operating point, and online clustering."""

    call_count: int
    ground_truth_campaign_count: int
    positive_pairs: int
    negative_pairs: int
    min_positive_score: float
    max_negative_score: float
    scenario_scores: dict[str, float]
    threshold_rows: tuple[PairwiseCounts, ...]
    operating: PairwiseCounts
    pipeline: PairwiseCounts
    ingest_rows: tuple[IngestRow, ...]
    example_association: CampaignAssociation
    rejection_example: CampaignAssociation
    config: ScoringConfig


def evaluate_dataset(
    dataset: SyntheticDataset,
    config: ScoringConfig | None = None,
) -> EvaluationReport:
    """Score every pair and ingest calls in time order."""
    active = config or ScoringConfig()
    runnable = prepare(dataset)
    features = _feature_map(runnable, active)
    truth = runnable.ground_truth()
    call_ids = [record.call_id for record in runnable.records()]
    scored_pairs = _scored_pairs(call_ids, features, truth, active)
    positive_scores = [score for same, score, _guard in scored_pairs if same]
    negative_scores = [score for same, score, _guard in scored_pairs if not same]
    scenario_scores = {
        name: score_features(features[left], features[right], active).association_score
        for name, left, right in SCENARIO_PAIRS
    }
    threshold_rows = tuple(
        _count_pairs(scored_pairs, threshold, guard=False, label=f"score>={threshold:.2f}")
        for threshold in REPORT_THRESHOLDS
    )
    operating = _count_pairs(
        scored_pairs,
        active.associate_threshold,
        guard=True,
        label="operating_point",
    )
    associations = _ingest(runnable, active)
    predicted = {item.call_id: item.campaign_id for item in associations}
    pipeline = _count_predicted(call_ids, truth, predicted, active.associate_threshold)
    example = next(item for item in associations if item.call_id == "irs-2")
    rejection = next(item for item in associations if item.call_id == "bank-1")
    return EvaluationReport(
        call_count=len(features),
        ground_truth_campaign_count=len(set(truth.values())),
        positive_pairs=len(positive_scores),
        negative_pairs=len(negative_scores),
        min_positive_score=min(positive_scores),
        max_negative_score=max(negative_scores),
        scenario_scores=scenario_scores,
        threshold_rows=threshold_rows,
        operating=operating,
        pipeline=pipeline,
        ingest_rows=tuple(
            IngestRow(
                call_id=item.call_id,
                ground_truth_campaign_id=truth[item.call_id],
                campaign_id=item.campaign_id,
                decision=item.decision,
                association_score=item.association_score,
                matched_call_id=item.matched_call_id,
            )
            for item in associations
        ),
        example_association=example,
        rejection_example=rejection,
        config=active,
    )


def render_markdown(report: EvaluationReport) -> str:
    """Render the committed evaluation report from a live measurement."""
    config = report.config
    lines = [
        "# WATSON deterministic scorer evaluation",
        "",
        "Synthetic labeled calls scored without embeddings or clustering.",
        "Pairwise labels are ground-truth campaign equality. A predicted positive",
        "means the two calls would be treated as the same campaign.",
        "",
        f"- Calls: {report.call_count}",
        f"- Ground-truth campaigns: {report.ground_truth_campaign_count}",
        f"- Same-campaign pairs: {report.positive_pairs}",
        f"- Different-campaign pairs: {report.negative_pairs}",
        f"- Minimum same-campaign score: {report.min_positive_score:.4f}",
        f"- Maximum different-campaign score: {report.max_negative_score:.4f}",
        f"- Gap: {report.min_positive_score - report.max_negative_score:.4f}",
        "",
        "## Operating point",
        "",
        f"- `associate_threshold`: {config.associate_threshold:.2f}",
        f"- Evidence guard: script group >= {config.min_script_group:.2f}, "
        f"or identifier group >= {config.min_identifier_group:.2f} "
        f"and script group >= {config.min_script_with_identifiers:.2f}",
        "- Missing features contribute 0. Weights are not renormalized.",
        "- Caller id is not a feature.",
        "",
        "Group weights:",
        "",
        "| group | weight |",
        "| --- | --- |",
    ]
    for name, weight in config.group_weights.items():
        lines.append(f"| {name} | {weight:.2f} |")
    lines.extend(["", "Leaf weights inside each group:", ""])
    lines.extend(_weight_table("script", config.script_weights))
    lines.extend(_weight_table("identifier", config.identifier_weights))
    lines.extend(_weight_table("structure", config.structure_weights))
    lines.extend(
        [
            "",
            (
                "Association score = "
                f"{config.group_weights['script']:.2f} * script + "
                f"{config.group_weights['identifier']:.2f} * identifier + "
                f"{config.group_weights['structure']:.2f} * structure,"
            ),
            "using the leaf weights above. Opening script score is the maximum of",
            "token Jaccard and a near-copy edit-distance bucket "
            f"(1.00 at ratio >= {config.edit_bucket_high:.2f}, "
            f"0.85 at ratio >= {config.edit_bucket_mid:.2f}, otherwise 0). "
            "Looser edit distance does not score.",
            "",
            "## Pairwise scores at fixed thresholds",
            "",
            "These rows use the score alone. The evidence guard is not applied.",
            "",
            "| threshold | TP | FP | FN | TN | precision | recall |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.threshold_rows:
        lines.append(_count_line(row))
    lines.extend(
        [
            "",
            "## Operating point (threshold and evidence guard)",
            "",
            "| rule | TP | FP | FN | TN | precision | recall |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            _named_count_line(report.operating),
            "",
            "## Online pipeline clustering",
            "",
            "Calls are ingested in time order. A pair is predicted positive when",
            "both calls land in the same assigned campaign. This is the decision",
            "the pipeline actually makes, including retrieval and transitivity.",
            "",
            "| rule | TP | FP | FN | TN | precision | recall |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            _named_count_line(report.pipeline),
            "",
            "| call | ground truth | decision | campaign | score | closest call |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.ingest_rows:
        closest = row.matched_call_id or ""
        lines.append(
            f"| {row.call_id} | {row.ground_truth_campaign_id} | {row.decision.value} "
            f"| {row.campaign_id} | {row.association_score:.4f} | {closest} |"
        )
    lines.extend(["", "## Scenario scores", ""])
    for name, _left, _right in SCENARIO_PAIRS:
        lines.append(f"- {name}: {report.scenario_scores[name]:.4f}")
    lines.extend(
        [
            "",
            "Partial-overlap pairs are "
            f"{report.scenario_scores['partial_irs_bank']:.4f} (IRS versus bank) and "
            f"{report.scenario_scores['partial_solar_insurance']:.4f} "
            "(solar versus insurance). Both stay under the "
            f"{config.associate_threshold:.2f} association threshold. "
            "Same-campaign pairs are at or above "
            f"{report.min_positive_score:.4f}.",
            "",
        ]
    )
    example = report.example_association
    rejection = report.rejection_example
    lines.extend(
        [
            "## Example association",
            "",
            f"`{example.call_id}` decision `{example.decision.value}` "
            f"campaign `{example.campaign_id}` score {example.association_score:.4f}.",
            "",
            "Reasons:",
            "",
        ]
    )
    for reason in example.reasons:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "Feature scores:",
            "",
            "| feature | score |",
            "| --- | --- |",
        ]
    )
    for name in LEAF_FEATURES:
        lines.append(f"| {name} | {example.feature_scores[name]:.4f} |")
    lines.extend(
        [
            "",
            "## Example rejection",
            "",
            f"`{rejection.call_id}` decision `{rejection.decision.value}` "
            f"campaign `{rejection.campaign_id}` score {rejection.association_score:.4f}.",
            "",
            "Reasons:",
            "",
        ]
    )
    for reason in rejection.reasons:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## Later comparison arm",
            "",
            "Embeddings and clustering are not part of this scorer. A later slice",
            "can measure them against this same labeled set and compare false",
            "merges, missed merges, and whether each positive decision still has",
            "a human-readable reason. This report is the baseline.",
            "",
        ]
    )
    recomputed = combine_association_score(example.feature_scores, config)
    if abs(recomputed - example.association_score) > 0.001:
        raise ValueError(
            f"example score {example.association_score} disagrees with formula {recomputed}"
        )
    return "\n".join(lines)


def _feature_map(
    runnable: RunnableDataset,
    config: ScoringConfig,
) -> dict[str, CallFeatures]:
    provider = runnable.provider()
    return {
        call.call_id: extract_features(call, provider.indicators_for(call), config)
        for call in runnable.calls()
    }


def _scored_pairs(
    call_ids: list[str],
    features: dict[str, CallFeatures],
    truth: dict[str, str],
    config: ScoringConfig,
) -> list[tuple[bool, float, bool]]:
    scored: list[tuple[bool, float, bool]] = []
    for index, left_id in enumerate(call_ids):
        for right_id in call_ids[index + 1 :]:
            breakdown = score_features(features[left_id], features[right_id], config)
            scored.append(
                (
                    truth[left_id] == truth[right_id],
                    breakdown.association_score,
                    evidence_guard_passes(breakdown.feature_scores, config),
                )
            )
    return scored


def _count_pairs(
    pairs: list[tuple[bool, float, bool]],
    threshold: float,
    guard: bool,
    label: str,
) -> PairwiseCounts:
    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0
    for same_campaign, score, guard_ok in pairs:
        predicted = score >= threshold and (guard_ok if guard else True)
        if predicted and same_campaign:
            true_positive += 1
        elif predicted and not same_campaign:
            false_positive += 1
        elif not predicted and same_campaign:
            false_negative += 1
        else:
            true_negative += 1
    return PairwiseCounts(
        label=label,
        threshold=threshold,
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        true_negative=true_negative,
        guard_applied=guard,
    )


def _ingest(
    runnable: RunnableDataset,
    config: ScoringConfig,
) -> list[CampaignAssociation]:
    pipeline = AssociationPipeline(intelligence=runnable.provider(), config=config)
    return [pipeline.ingest(call) for call in runnable.calls()]


def _count_predicted(
    call_ids: list[str],
    truth: dict[str, str],
    predicted: dict[str, str],
    threshold: float,
) -> PairwiseCounts:
    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0
    for index, left_id in enumerate(call_ids):
        for right_id in call_ids[index + 1 :]:
            same_campaign = truth[left_id] == truth[right_id]
            predicted_same = predicted[left_id] == predicted[right_id]
            if predicted_same and same_campaign:
                true_positive += 1
            elif predicted_same and not same_campaign:
                false_positive += 1
            elif not predicted_same and same_campaign:
                false_negative += 1
            else:
                true_negative += 1
    return PairwiseCounts(
        label="pipeline",
        threshold=threshold,
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        true_negative=true_negative,
        guard_applied=True,
    )


def _weight_table(title: str, weights: dict[str, float]) -> list[str]:
    lines = [f"### {title}", "", "| feature | weight |", "| --- | --- |"]
    for name, weight in weights.items():
        lines.append(f"| {name} | {weight:.2f} |")
    lines.append("")
    return lines


def _count_line(row: PairwiseCounts) -> str:
    return (
        f"| {row.threshold:.2f} | {row.true_positive} | {row.false_positive} "
        f"| {row.false_negative} | {row.true_negative} "
        f"| {row.precision:.3f} | {row.recall:.3f} |"
    )


def _named_count_line(row: PairwiseCounts) -> str:
    return (
        f"| {row.label} | {row.true_positive} | {row.false_positive} "
        f"| {row.false_negative} | {row.true_negative} "
        f"| {row.precision:.3f} | {row.recall:.3f} |"
    )
