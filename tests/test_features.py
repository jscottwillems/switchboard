"""Feature extraction and the SHERLOCK fixture adapter."""

import pytest

from watson.config import ScoringConfig
from watson.features import admitted_observations, extract_features
from watson.models import CallFeatures
from watson.sherlock.mock import FixtureIntelligenceProvider
from watson.sherlock.models import IntelligenceObservation, ObservationKind
from tests.helpers import make_call


def test_caller_id_is_not_a_scoring_feature() -> None:
    assert "caller_id" not in CallFeatures.model_fields


def test_low_confidence_observations_are_dropped(config: ScoringConfig) -> None:
    call = make_call("bank-x", "Your account is on hold at First National Bank.")
    observations = [
        IntelligenceObservation(
            kind=ObservationKind.CLAIMED_ORGANIZATION,
            value="First National Bank",
            confidence=0.95,
        ),
        IntelligenceObservation(
            kind=ObservationKind.CLAIMED_ORGANIZATION,
            value="Internal Revenue Service",
            confidence=0.15,
            evidence="guess",
        ),
    ]
    kept = admitted_observations(observations, config)
    assert [item.value for item in kept] == ["First National Bank"]
    features = extract_features(
        call,
        FixtureIntelligenceProvider({"bank-x": observations}).indicators_for(call),
        config,
    )
    assert features.claimed_organizations == frozenset({"first national bank"})


def test_opening_observation_overrides_the_transcript_span(config: ScoringConfig) -> None:
    call = make_call("c1", "alpha bravo charlie delta echo foxtrot golf hotel")
    provider = FixtureIntelligenceProvider(
        {
            "c1": [
                IntelligenceObservation(
                    kind=ObservationKind.OPENING_SCRIPT,
                    value="unique opening phrase about a federal refund",
                    confidence=0.9,
                )
            ]
        }
    )
    features = extract_features(call, provider.indicators_for(call), config)
    assert "refund" in features.opening_tokens
    assert "alpha" not in features.opening_tokens


def test_ivr_observation_is_used_when_the_call_path_is_empty(config: ScoringConfig) -> None:
    call = make_call("c1", "hello there from support")
    provider = FixtureIntelligenceProvider(
        {
            "c1": [
                IntelligenceObservation(
                    kind=ObservationKind.IVR_STRUCTURE,
                    value="greeting > ssn_prompt > refund_agent",
                    confidence=0.9,
                )
            ]
        }
    )
    features = extract_features(call, provider.indicators_for(call), config)
    assert features.ivr_path == ("greeting", "ssn_prompt", "refund_agent")


def test_call_ivr_path_wins_over_observation(config: ScoringConfig) -> None:
    call = make_call("c1", "hello there", ivr_path=["only_step"])
    provider = FixtureIntelligenceProvider(
        {
            "c1": [
                IntelligenceObservation(
                    kind=ObservationKind.IVR_STRUCTURE,
                    value="greeting > other",
                    confidence=0.99,
                )
            ]
        }
    )
    features = extract_features(call, provider.indicators_for(call), config)
    assert features.ivr_path == ("only_step",)


def test_mismatched_intelligence_call_id_is_rejected(config: ScoringConfig) -> None:
    call = make_call("c1", "hello there")
    other = FixtureIntelligenceProvider({}).indicators_for(make_call("c2", "hello there"))
    with pytest.raises(ValueError, match="does not match"):
        extract_features(call, other, config)
