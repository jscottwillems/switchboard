"""Adapter boundary between WATSON and Sherlock findings."""

from typing import Protocol

from switchboard_schemas.interpretations import IntelligenceFinding

from watson.models import CompletedCall


class FindingProvider(Protocol):
    """Supply `IntelligenceFinding` rows for a completed call.

    Import path: `switchboard_schemas.interpretations.IntelligenceFinding`
    (`packages/schemas`). Sherlock proposes findings. WATSON does not invent
    finding kinds or campaign ids.
    """

    def findings_for(self, call: CompletedCall) -> list[IntelligenceFinding]:
        """Return findings for this call. Unknown calls return an empty list."""
