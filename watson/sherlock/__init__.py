"""Sherlock finding adapter. The live model is `IntelligenceFinding`."""

from watson.sherlock.interface import FindingProvider
from watson.sherlock.mock import FixtureFindingProvider

__all__ = [
    "FindingProvider",
    "FixtureFindingProvider",
]
