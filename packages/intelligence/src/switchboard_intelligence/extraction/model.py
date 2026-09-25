"""Model-based extraction plug-in.

Deterministic rules cover obvious surface forms. When a span is paraphrased,
spoken as words, or outside the lexicon, a model extractor may add
observations. This milestone ships the interface and a null implementation
that returns nothing. A model result must still be an Observation: a verbatim
transcript span with an explicit confidence, not an Inference.
"""

from collections.abc import Sequence
from typing import Protocol

from switchboard_intelligence.schemas.observation import Observation
from switchboard_intelligence.schemas.transcript import Transcript


class ModelExtractor(Protocol):
    """Add observations the rule extractor did not produce.

    Implementations must not mutate `transcript` or `deterministic`.
    """

    name: str

    def extract(
        self,
        transcript: Transcript,
        deterministic: Sequence[Observation],
    ) -> list[Observation]:
        """Return additional observations."""


class NullModelExtractor:
    """Stand-in until a model extractor is wired in.

    `extract` returns an empty list. Callers that omit a model extractor
    never invoke this class; it exists so the plug-in point can be tested.
    """

    name = "model.null"

    def extract(
        self,
        transcript: Transcript,
        deterministic: Sequence[Observation],
    ) -> list[Observation]:
        return []
