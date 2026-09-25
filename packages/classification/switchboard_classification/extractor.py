"""Finding extraction port. Owner: SHERLOCK. Runs off the audio hot path."""

from typing import Protocol, Sequence

from switchboard_schemas.interpretations import IntelligenceFinding
from switchboard_schemas.observations import TranscriptSegment


class FindingExtractor(Protocol):
    def extract(self, segments: Sequence[TranscriptSegment]) -> list[IntelligenceFinding]:
        """Propose findings. Each finding must cite transcript segments."""


class NullFindingExtractor:
    def extract(self, segments: Sequence[TranscriptSegment]) -> list[IntelligenceFinding]:
        del segments
        return []
