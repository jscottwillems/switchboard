"""Fixture-backed intelligence provider used until SHERLOCK is wired."""

from collections.abc import Mapping, Sequence

from watson.models import CompletedCall
from watson.sherlock.models import CallIntelligence, IntelligenceObservation


class FixtureIntelligenceProvider:
    """Return prebuilt observations keyed by call id.

    Unknown call ids yield an empty observation list so the scorer still
    runs on transcript and call-structure features.
    """

    def __init__(
        self,
        observations_by_call: Mapping[str, Sequence[IntelligenceObservation]],
    ) -> None:
        self._observations = {
            call_id: list(observations)
            for call_id, observations in observations_by_call.items()
        }

    def indicators_for(self, call: CompletedCall) -> CallIntelligence:
        return CallIntelligence(
            call_id=call.call_id,
            observations=list(self._observations.get(call.call_id, [])),
        )
