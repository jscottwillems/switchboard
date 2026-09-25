"""Loki handoff lists every observation kind once, in elicit order."""

from pathlib import Path

from switchboard_intelligence.handoff import ELICIT_GROUPS, ELICIT_RANK, GOAL_IDS
from switchboard_intelligence.schemas import ObservationKind

STATUS_PATH = Path(__file__).resolve().parents[3] / "docs" / "STATUS.md"


def test_loki_elicit_groups() -> None:
    assert [kinds for _rank, kinds in ELICIT_GROUPS] == [
        (ObservationKind.PRETEXT_CATEGORY,),
        (ObservationKind.CLAIMED_COMPANY,),
        (ObservationKind.LOAN_AMOUNTS, ObservationKind.RATES, ObservationKind.FEES),
        (
            ObservationKind.CALLBACK_NUMBERS,
            ObservationKind.SPOKEN_NUMBERS,
            ObservationKind.CASE_OR_REFERENCE_IDS,
            ObservationKind.SPOKEN_CLI_CLAIM,
        ),
        (ObservationKind.CLAIMED_AGENT, ObservationKind.CLAIMED_DEPARTMENT),
        (ObservationKind.DOMAINS, ObservationKind.URLS, ObservationKind.EMAIL_ADDRESSES),
        (ObservationKind.PAYMENT_METHODS, ObservationKind.REMOTE_ACCESS_TOOLS),
        (ObservationKind.REQUESTED_INFORMATION,),
        (
            ObservationKind.SCRIPT_PHRASES,
            ObservationKind.URGENCY_LANGUAGE,
            ObservationKind.THREAT_OR_CONSEQUENCE_LANGUAGE,
            ObservationKind.TRANSFER_EVENTS,
            ObservationKind.SPOOFED_AUTHORITY_CLAIMS,
            ObservationKind.OPENING_SCRIPT_TEXT,
            ObservationKind.IVR_PROMPTS,
            ObservationKind.IVR_MENU_PATH,
            ObservationKind.TRANSFER_DESTINATION_CLAIMED,
            ObservationKind.SCRIPT_LANGUAGE,
        ),
        (ObservationKind.FOLLOW_UP_PROMISES,),
        (ObservationKind.OTHER,),
    ]
    assert GOAL_IDS == tuple(kind.value for kind, _reason in ELICIT_RANK)


def test_elicit_rank_is_a_permutation_of_observation_kinds() -> None:
    kinds = [kind for kind, _reason in ELICIT_RANK]
    assert len(kinds) == len(set(kinds))
    assert set(kinds) == set(ObservationKind)


def test_status_names_watson_shapes() -> None:
    from switchboard_intelligence.handoff import WATSON_FEATURES

    text = STATUS_PATH.read_text(encoding="utf-8")
    watson = text.split("## HANDOFF — Sherlock → Watson", 1)[1]
    assert "CampaignAssociation" in watson
    assert "Observation" in watson
    assert "Inference" in watson
    tier_at = [watson.index(f"### Tier {tier}") for tier in ("A", "B", "C")]
    assert tier_at == sorted(tier_at)
    positions = [watson.index(f"`{feature}`") for _tier, _shape, feature, _note in WATSON_FEATURES]
    assert positions == sorted(positions)


def test_status_handoff_follows_elicit_rank() -> None:
    text = STATUS_PATH.read_text(encoding="utf-8")
    assert "ATLAS owns the full status-doc structure" in text
    section = text.split("## HANDOFF", 1)[1]
    kind_positions = [section.index(f"`{kind.value}`") for kind, _reason in ELICIT_RANK]
    reason_positions = [section.index(reason) for _kind, reason in ELICIT_RANK]
    assert kind_positions == sorted(kind_positions)
    assert reason_positions == sorted(reason_positions)
