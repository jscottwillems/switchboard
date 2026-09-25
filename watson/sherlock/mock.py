"""Fixture-backed provider used until Sherlock's package is on main."""

from collections.abc import Mapping

from watson.models import CompletedCall
from watson.sherlock.models import CallIntelligence


class FixtureIntelligenceProvider:
    """Return prebuilt CallIntelligence records keyed by call id."""

    def __init__(self, intelligence_by_call: Mapping[str, CallIntelligence]) -> None:
        self._intelligence = dict(intelligence_by_call)

    def indicators_for(self, call: CompletedCall) -> CallIntelligence:
        found = self._intelligence.get(call.call_id)
        if found is None:
            return CallIntelligence(call_id=call.call_id, observations=[], inference=None)
        return found
