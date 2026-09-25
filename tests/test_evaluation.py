"""Synthetic dataset coverage and the measured false-positive / false-negative report."""

from pathlib import Path

from watson.config import ScoringConfig
from watson.dataset import ScenarioTag, default_report_path, load_dataset
from watson.evaluate import evaluate_dataset, render_markdown
from watson.sherlock.models import ObservationKind
from watson.synthetic import build_dataset


def test_dataset_covers_the_required_scenarios() -> None:
    dataset = build_dataset()
    tags = {tag for record in dataset.calls for tag in record.scenario_tags}
    assert tags == set(ScenarioTag)
    campaigns = {record.ground_truth_campaign_id for record in dataset.calls}
    assert len(campaigns) >= 6
    records = {record.call_id: record for record in dataset.calls}
    assert records["irs-4"].caller_id == records["tech-3"].caller_id
    assert records["irs-4"].ground_truth_campaign_id != records["tech-3"].ground_truth_campaign_id
    assert records["irs-1"].ground_truth_campaign_id == records["irs-4"].ground_truth_campaign_id
    irs_callbacks = {
        observation.value
        for record in (records["irs-1"], records["irs-4"])
        for observation in record.observations
        if observation.kind.value == "callback_identifier" and observation.confidence >= 0.5
    }
    assert len(irs_callbacks) == 2


def test_committed_dataset_matches_the_builder() -> None:
    assert load_dataset() == build_dataset()


def test_operating_point_has_no_false_merges_or_misses() -> None:
    report = evaluate_dataset(build_dataset())
    threshold = ScoringConfig().associate_threshold
    assert report.max_negative_score + 0.2 <= threshold <= report.min_positive_score - 0.2
    assert report.positive_pairs == 11
    assert report.negative_pairs == 94
    assert report.call_count == 15
    assert report.ground_truth_campaign_count == 8
    assert report.operating.false_positive == 0
    assert report.operating.false_negative == 0
    assert report.operating.precision == 1.0
    assert report.operating.recall == 1.0
    assert report.pipeline.false_positive == 0
    assert report.pipeline.false_negative == 0
    assert report.scenario_scores["partial_irs_bank"] < threshold
    assert report.scenario_scores["partial_solar_insurance"] < threshold
    assert report.scenario_scores["repeat_caller_different_campaign"] < threshold
    assert report.scenario_scores["changing_identifiers_irs"] >= threshold
    assert report.scenario_scores["clearly_related_irs"] >= threshold


def test_docs_name_the_threshold_and_observation_kinds() -> None:
    scoring = Path("docs/watson/SCORING.md").read_text(encoding="utf-8")
    adapter = Path("docs/watson/SHERLOCK_ADAPTER.md").read_text(encoding="utf-8")
    assert f"{ScoringConfig().associate_threshold:.2f}" in scoring
    assert "Caller id is stored on the call record and is not a feature" in scoring
    for kind in ObservationKind:
        assert kind.value in adapter


def test_committed_report_matches_a_fresh_evaluation() -> None:
    report = evaluate_dataset(load_dataset())
    assert default_report_path().read_text(encoding="utf-8") == render_markdown(report)
    assert "Embeddings and clustering are not part of this scorer." in render_markdown(report)
