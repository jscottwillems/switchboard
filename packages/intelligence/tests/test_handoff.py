"""Loki handoff lists every observation kind once, in elicit order."""

from pathlib import Path

from switchboard_intelligence.handoff import ELICIT_RANK
from switchboard_intelligence.schemas import ObservationKind

STATUS_PATH = Path(__file__).resolve().parents[3] / "docs" / "STATUS.md"


def test_elicit_rank_is_a_permutation_of_observation_kinds() -> None:
    kinds = [kind for kind, _reason in ELICIT_RANK]
    assert len(kinds) == len(set(kinds))
    assert set(kinds) == set(ObservationKind)


def test_status_handoff_follows_elicit_rank() -> None:
    text = STATUS_PATH.read_text(encoding="utf-8")
    assert "ATLAS owns the full status-doc structure" in text
    section = text.split("## HANDOFF", 1)[1]
    kind_positions = [section.index(f"`{kind.value}`") for kind, _reason in ELICIT_RANK]
    reason_positions = [section.index(reason) for _kind, reason in ELICIT_RANK]
    assert kind_positions == sorted(kind_positions)
    assert reason_positions == sorted(reason_positions)
