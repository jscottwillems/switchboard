"""Adapter boundary between WATSON and call-intelligence indicators."""

from typing import Protocol

from watson.models import CompletedCall
from watson.sherlock.models import CallIntelligence


class CallIntelligenceProvider(Protocol):
    """Supply typed indicators for a completed call.

    Implementations may be a fixture, a future SHERLOCK client, or a test
    double. WATSON does not discover entities itself beyond transcript
    tokens, timing, duration, transfer, and IVR path on the call record.
    """

    def indicators_for(self, call: CompletedCall) -> CallIntelligence:
        """Return observations for `call`. The call_id must match."""
