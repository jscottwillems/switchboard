"""SB-011: shared callback_number E.164 values open one hypothesized campaign."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from switchboard_classification import (
    CorrelationInput,
    ExactCallbackCorrelator,
    NullCampaignCorrelator,
)
from switchboard_classification.correlator import (
    EXACT_CALLBACK_CONFIDENCE,
    EXACT_CALLBACK_METHOD,
    EXACT_CALLBACK_METHOD_VERSION,
)
from switchboard_schemas.enums import (
    CampaignStatus,
    FindingKind,
    FindingStatus,
    RecordLayer,
)
from switchboard_schemas.interpretations import IntelligenceFinding

NOW = datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc)
SHARED = "+15551234567"
OTHER = "+15557654321"


def _finding(
    call_session_id: UUID,
    value: str,
    *,
    kind: FindingKind = FindingKind.CALLBACK_NUMBER,
    status: FindingStatus = FindingStatus.PROPOSED,
    created_at: datetime = NOW,
    finding_id: UUID | None = None,
) -> IntelligenceFinding:
    return IntelligenceFinding(
        id=finding_id or uuid4(),
        call_session_id=call_session_id,
        kind=kind,
        value=value,
        raw_quote=value,
        transcript_segment_ids=[uuid4()],
        extractor="e164",
        extractor_version="0.1.0",
        confidence=1.0,
        status=status,
        created_at=created_at,
    )


def _input(call_session_id: UUID, findings: list[IntelligenceFinding]) -> CorrelationInput:
    return CorrelationInput(call_session_id=call_session_id, findings=findings)


def test_shared_callback_opens_one_hypothesized_campaign_and_two_attributions() -> None:
    left_call = uuid4()
    right_call = uuid4()
    left_finding = _finding(left_call, SHARED, created_at=NOW)
    right_finding = _finding(right_call, SHARED, created_at=NOW + timedelta(seconds=30))
    correlator = ExactCallbackCorrelator()

    assert correlator.propose(_input(left_call, [left_finding])) == []
    assert correlator.campaigns() == []

    opened = correlator.propose(_input(right_call, [right_finding]))
    campaigns = correlator.campaigns()
    assert len(campaigns) == 1
    campaign = campaigns[0]
    assert campaign.record_layer is RecordLayer.ATTRIBUTION
    assert campaign.status is CampaignStatus.HYPOTHESIZED
    assert campaign.label == f"callback {SHARED}"
    assert campaign.summary is not None
    assert FindingKind.CALLBACK_NUMBER.value in campaign.summary
    assert SHARED in campaign.summary
    assert campaign.created_at == left_finding.created_at
    assert campaign.updated_at == right_finding.created_at

    assert len(opened) == 2
    assert opened == correlator.attributions()
    by_call = {row.call_session_id: row for row in opened}
    assert set(by_call) == {left_call, right_call}
    for call_id, finding in ((left_call, left_finding), (right_call, right_finding)):
        row = by_call[call_id]
        assert row.record_layer is RecordLayer.ATTRIBUTION
        assert row.campaign_id == campaign.id
        assert row.supporting_finding_ids == [finding.id]
        assert row.method == EXACT_CALLBACK_METHOD
        assert row.method_version == EXACT_CALLBACK_METHOD_VERSION
        assert row.confidence == EXACT_CALLBACK_CONFIDENCE
        assert FindingKind.CALLBACK_NUMBER.value in row.rationale
        assert SHARED in row.rationale
        assert row.created_at == finding.created_at
    assert by_call[left_call].supporting_finding_ids != by_call[right_call].supporting_finding_ids


def test_distinct_callback_numbers_do_not_merge() -> None:
    left_call = uuid4()
    right_call = uuid4()
    correlator = ExactCallbackCorrelator()
    assert correlator.propose(_input(left_call, [_finding(left_call, SHARED)])) == []
    assert correlator.propose(_input(right_call, [_finding(right_call, OTHER)])) == []
    assert correlator.campaigns() == []
    assert correlator.attributions() == []


def test_later_call_joins_the_same_campaign() -> None:
    calls = [uuid4(), uuid4(), uuid4()]
    correlator = ExactCallbackCorrelator()
    correlator.propose(_input(calls[0], [_finding(calls[0], SHARED, created_at=NOW)]))
    correlator.propose(
        _input(calls[1], [_finding(calls[1], SHARED, created_at=NOW + timedelta(seconds=1))])
    )
    campaign_id = correlator.campaigns()[0].id
    joined = correlator.propose(
        _input(calls[2], [_finding(calls[2], SHARED, created_at=NOW + timedelta(seconds=2))])
    )
    assert len(joined) == 1
    assert joined[0].call_session_id == calls[2]
    assert joined[0].campaign_id == campaign_id
    assert len(correlator.campaigns()) == 1
    assert {row.call_session_id for row in correlator.attributions()} == set(calls)


def test_two_shared_numbers_stay_two_campaigns() -> None:
    first = uuid4()
    second = uuid4()
    third = uuid4()
    correlator = ExactCallbackCorrelator()
    correlator.propose(
        _input(
            first,
            [_finding(first, SHARED, created_at=NOW), _finding(first, OTHER, created_at=NOW)],
        )
    )
    correlator.propose(
        _input(second, [_finding(second, SHARED, created_at=NOW + timedelta(seconds=1))])
    )
    correlator.propose(
        _input(third, [_finding(third, OTHER, created_at=NOW + timedelta(seconds=2))])
    )
    campaigns = correlator.campaigns()
    assert len(campaigns) == 2
    assert {campaign.label for campaign in campaigns} == {f"callback {SHARED}", f"callback {OTHER}"}
    assert all(campaign.status is CampaignStatus.HYPOTHESIZED for campaign in campaigns)
    by_campaign = {campaign.label: campaign.id for campaign in campaigns}
    rows = correlator.attributions()
    assert len(rows) == 4
    shared_id = by_campaign[f"callback {SHARED}"]
    other_id = by_campaign[f"callback {OTHER}"]
    shared_calls = {row.call_session_id for row in rows if row.campaign_id == shared_id}
    other_calls = {row.call_session_id for row in rows if row.campaign_id == other_id}
    assert shared_calls == {first, second}
    assert other_calls == {first, third}


def test_only_a_second_session_with_the_same_e164_opens_a_campaign() -> None:
    call_id = uuid4()
    other_call = uuid4()
    correlator = ExactCallbackCorrelator()
    finding = _finding(call_id, SHARED)
    assert correlator.propose(_input(call_id, [finding])) == []
    assert correlator.propose(_input(call_id, [finding])) == []
    assert correlator.campaigns() == []

    rejected = ExactCallbackCorrelator()
    rejected.propose(
        _input(call_id, [_finding(call_id, SHARED, status=FindingStatus.REJECTED)])
    )
    rejected.propose(
        _input(other_call, [_finding(other_call, SHARED, status=FindingStatus.REJECTED)])
    )
    assert rejected.campaigns() == []

    formatted = ExactCallbackCorrelator()
    formatted.propose(_input(call_id, [_finding(call_id, "(555) 123-4567")]))
    formatted.propose(_input(other_call, [_finding(other_call, "(555) 123-4567")]))
    assert formatted.campaigns() == []

    pretext = ExactCallbackCorrelator()
    pretext.propose(
        _input(call_id, [_finding(call_id, SHARED, kind=FindingKind.PRETEXT)])
    )
    pretext.propose(
        _input(other_call, [_finding(other_call, SHARED, kind=FindingKind.PRETEXT)])
    )
    assert pretext.campaigns() == []

    mismatched = ExactCallbackCorrelator()
    foreign = _finding(other_call, SHARED)
    mismatched.propose(_input(call_id, [foreign]))
    mismatched.propose(_input(other_call, [_finding(uuid4(), SHARED)]))
    assert mismatched.campaigns() == []

    accepted = ExactCallbackCorrelator()
    accepted.propose(_input(call_id, [_finding(call_id, SHARED, status=FindingStatus.ACCEPTED)]))
    opened = accepted.propose(_input(other_call, [_finding(other_call, SHARED)]))
    assert len(accepted.campaigns()) == 1
    assert {row.call_session_id for row in opened} == {call_id, other_call}


def test_pending_findings_are_cited_when_the_campaign_opens() -> None:
    left_call = uuid4()
    right_call = uuid4()
    earlier = _finding(left_call, SHARED, created_at=NOW)
    later = _finding(left_call, SHARED, created_at=NOW + timedelta(seconds=5))
    partner = _finding(right_call, SHARED, created_at=NOW + timedelta(seconds=9))
    correlator = ExactCallbackCorrelator()
    correlator.propose(_input(left_call, [later]))
    correlator.propose(_input(left_call, [earlier]))
    correlator.propose(_input(right_call, [partner]))
    rows = {row.call_session_id: row for row in correlator.attributions()}
    assert rows[left_call].supporting_finding_ids == [earlier.id, later.id]
    assert rows[right_call].supporting_finding_ids == [partner.id]


def test_replay_does_not_open_a_second_campaign() -> None:
    left_call = uuid4()
    right_call = uuid4()
    left_finding_id = uuid4()
    right_finding_id = uuid4()
    left = _finding(left_call, SHARED, finding_id=left_finding_id)
    right = _finding(
        right_call,
        SHARED,
        finding_id=right_finding_id,
        created_at=NOW + timedelta(seconds=1),
    )

    first = ExactCallbackCorrelator()
    first.propose(_input(left_call, [left]))
    first.propose(_input(right_call, [right]))
    again = first.propose(_input(right_call, [right]))
    assert again == []
    assert len(first.campaigns()) == 1
    assert len(first.attributions()) == 2

    second = ExactCallbackCorrelator()
    second.propose(_input(left_call, [left]))
    second.propose(_input(right_call, [right]))
    assert second.campaigns()[0].id == first.campaigns()[0].id
    assert [row.id for row in second.attributions()] == [row.id for row in first.attributions()]


def test_null_correlator_still_returns_nothing() -> None:
    call_id = uuid4()
    item = _input(call_id, [_finding(call_id, SHARED)])
    assert NullCampaignCorrelator().propose(item) == []
