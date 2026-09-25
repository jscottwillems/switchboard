"""Attribution plug-in.

Linking a call to a campaign or actor needs a corpus this milestone does
not include. The schema lives in `schemas.attribution`. The default
attributor returns no records.
"""

from collections.abc import Sequence
from typing import Protocol

from switchboard_intelligence.schemas.attribution import Attribution
from switchboard_intelligence.schemas.inference import Inference
from switchboard_intelligence.schemas.observation import Observation


class Attributor(Protocol):
    name: str

    def attribute(
        self,
        call_id: str,
        observations: Sequence[Observation],
        inferences: Sequence[Inference],
    ) -> list[Attribution]:
        """Return attributions supported by the call's intelligence."""


class NoCampaignCorpusAttributor:
    """No campaign corpus is loaded. Returns an empty list."""

    name = "attribution.none"

    def attribute(
        self,
        call_id: str,
        observations: Sequence[Observation],
        inferences: Sequence[Inference],
    ) -> list[Attribution]:
        return []
