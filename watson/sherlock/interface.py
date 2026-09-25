"""Adapter boundary between WATSON and Sherlock's correlation contract."""

from typing import Protocol

from watson.models import CompletedCall
from watson.sherlock.models import CallIntelligence


class CallIntelligenceProvider(Protocol):
    """Supply observations and the correlation inference for a completed call.

    Expected import once Sherlock publishes the correlation models on main:

    `switchboard_intelligence.schemas.observation.Observation`
    `switchboard_intelligence.schemas.inference` (correlation fields)

    Call-layer metadata (CLI/ANI, timing, duration, simultaneous calls) stays
    on `CompletedCall`. It is not an Observation.
    """

    def indicators_for(self, call: CompletedCall) -> CallIntelligence:
        """Return observations and inference. `call_id` values must match."""
