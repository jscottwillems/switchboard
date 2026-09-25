"""End-to-end ingest: retrieval, decision, events, and explainable results."""

from watson.config import ScoringConfig
from watson.dataset import SyntheticDataset, prepare
from watson.events import InMemoryEventEmitter
from watson.models import DecisionAction
from watson.pipeline import AssociationPipeline
from watson.sherlock.mock import FixtureIntelligenceProvider
from tests.helpers import make_call

_IDENTICAL_PITCH = (
    "Please stay with the refund verification department while we confirm "
    "the filing discrepancy and release the federal refund to the taxpayer."
)


def _run(dataset: SyntheticDataset, config: ScoringConfig | None = None):
    runnable = prepare(dataset)
    emitter = InMemoryEventEmitter()
    pipeline = AssociationPipeline(
        intelligence=runnable.provider(),
        emitter=emitter,
        config=config,
    )
    associations = [pipeline.ingest(call) for call in runnable.calls()]
    return associations, emitter


def test_pipeline_matches_ground_truth_partition(dataset: SyntheticDataset) -> None:
    associations, emitter = _run(dataset)
    truth = {record.call_id: record.ground_truth_campaign_id for record in dataset.calls}
    predicted = {item.call_id: item.campaign_id for item in associations}
    call_ids = list(predicted)
    for index, left in enumerate(call_ids):
        for right in call_ids[index + 1 :]:
            assert (truth[left] == truth[right]) == (predicted[left] == predicted[right])
    assert len(emitter.events) == len(dataset.calls)
    sample = emitter.events[1]
    assert sample.event_type == "campaign.association.decided"
    assert sample.producer == "watson"
    assert sample.event_id == "campaign.association.decided:irs-2"
    assert sample.association.reasons


def test_pipeline_is_deterministic(dataset: SyntheticDataset) -> None:
    first, _emitter = _run(dataset)
    second, _emitter = _run(dataset)
    assert [(item.call_id, item.campaign_id, item.association_score) for item in first] == [
        (item.call_id, item.campaign_id, item.association_score) for item in second
    ]


def test_partial_overlap_is_retrieved_and_rejected(dataset: SyntheticDataset) -> None:
    associations, _emitter = _run(dataset)
    by_id = {item.call_id: item for item in associations}
    bank = by_id["bank-1"]
    insurance = by_id["insurance-1"]
    assert bank.decision is DecisionAction.NEW_CAMPAIGN
    assert bank.matched_call_id is not None
    assert bank.matched_call_id.startswith("irs-")
    assert bank.association_score < bank.threshold
    assert bank.feature_scores["claimed_company_normalized"] == 0.0
    assert "below threshold" in bank.reasons[0]
    assert insurance.decision is DecisionAction.NEW_CAMPAIGN
    assert insurance.association_score < insurance.threshold
    assert insurance.matched_call_id == "solar-1"


def test_changing_identifiers_still_join_and_repeat_caller_does_not(
    dataset: SyntheticDataset,
) -> None:
    associations, _emitter = _run(dataset)
    by_id = {item.call_id: item for item in associations}
    irs_4 = by_id["irs-4"]
    tech_3 = by_id["tech-3"]
    assert irs_4.decision is DecisionAction.ASSOCIATE
    assert irs_4.campaign_id == by_id["irs-1"].campaign_id
    assert irs_4.feature_scores["phone_e164"] == 0.0
    assert irs_4.feature_scores["email_domain_registrable"] == ScoringConfig().email_domain_score
    assert (
        f"opening_script_text score {irs_4.feature_scores['opening_script_text']:.2f}"
        in " ".join(irs_4.reasons)
    )
    assert "phone_e164" in " ".join(by_id["irs-2"].reasons)
    assert "claimed_company_normalized" in " ".join(irs_4.reasons)
    assert tech_3.campaign_id != irs_4.campaign_id
    records = {record.call_id: record for record in dataset.calls}
    assert records["irs-4"].caller_id == records["tech-3"].caller_id


def test_script_only_near_copy_stays_below_threshold() -> None:
    pipeline = AssociationPipeline(intelligence=FixtureIntelligenceProvider({}))
    first = pipeline.ingest(make_call("n1", _IDENTICAL_PITCH))
    second = pipeline.ingest(
        make_call(
            "n2",
            _IDENTICAL_PITCH,
            start="2026-04-02T14:01:00",
            end="2026-04-02T14:04:00",
        )
    )
    assert first.decision is DecisionAction.NEW_CAMPAIGN
    assert second.decision is DecisionAction.NEW_CAMPAIGN
    assert second.campaign_id != first.campaign_id
    assert second.association_score < second.threshold
    assert second.feature_scores["opening_script_text"] == 1.0
    assert second.feature_scores["phone_e164"] == 0.0


def test_structure_features_alone_do_not_associate() -> None:
    pipeline = AssociationPipeline(intelligence=FixtureIntelligenceProvider({}))
    first = pipeline.ingest(make_call("s1", "alpha bravo charlie delta"))
    second = pipeline.ingest(
        make_call(
            "s2",
            "hotel india juliet kilo",
            start="2026-04-02T14:01:00",
            end="2026-04-02T14:04:00",
        )
    )
    assert second.decision is DecisionAction.NEW_CAMPAIGN
    assert second.campaign_id != first.campaign_id
    assert second.association_score == 0.0
    assert second.feature_scores["timing"] == 1.0
    assert second.feature_scores["ivr_prompts"] == 0.0


def test_high_threshold_opens_a_campaign_per_call(dataset: SyntheticDataset) -> None:
    associations, _emitter = _run(dataset, ScoringConfig(associate_threshold=0.999))
    assert len({item.campaign_id for item in associations}) == len(dataset.calls)
    assert all(item.decision is DecisionAction.NEW_CAMPAIGN for item in associations)
