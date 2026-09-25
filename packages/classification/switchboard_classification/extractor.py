"""Finding extraction port. Owner: SHERLOCK. Runs off the audio hot path.

SB-009 proposes `interp.intelligence_finding` rows. It does not write
observation tables. Further finding kinds need a `FindingKind` change in
`packages/schemas` from ATLAS before this extractor emits them.
"""

import re
from typing import Protocol, Sequence
from uuid import UUID, uuid5

from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import FindingKind, FindingStatus
from switchboard_schemas.interpretations import IntelligenceFinding
from switchboard_schemas.observations import TranscriptSegment

EXTRACTOR_NAME = "e164"
EXTRACTOR_VERSION = "0.1.0"
# Certainty the rule ran, not a probability the number is a real callback.
E164_CONFIDENCE = 1.0

# A literal E.164 token. Formatted NANP text without a leading plus is not one.
_E164_IN_TEXT = re.compile(r"(?:^|(?<=\s))\+[1-9]\d{1,14}(?!\d)")


class FindingExtractor(Protocol):
    def extract(self, segments: Sequence[TranscriptSegment]) -> list[IntelligenceFinding]:
        """Propose findings. Each finding must cite transcript segments."""


class NullFindingExtractor:
    def extract(self, segments: Sequence[TranscriptSegment]) -> list[IntelligenceFinding]:
        del segments
        return []


class E164FindingExtractor:
    """One proposed callback_number per distinct E.164 in a segment.

    A segment with no E.164 token yields nothing.
    """

    def extract(self, segments: Sequence[TranscriptSegment]) -> list[IntelligenceFinding]:
        findings: list[IntelligenceFinding] = []
        ordered = sorted(segments, key=lambda item: (item.sequence, str(item.id)))
        for segment in ordered:
            seen: set[str] = set()
            for match in _E164_IN_TEXT.finditer(segment.text):
                value = match.group(0)
                if value in seen:
                    continue
                seen.add(value)
                findings.append(_callback_finding(segment, value))
        return findings


def _callback_finding(segment: TranscriptSegment, value: str) -> IntelligenceFinding:
    return IntelligenceFinding(
        id=_finding_id(segment.call_session_id, segment.id, value),
        call_session_id=segment.call_session_id,
        kind=FindingKind.CALLBACK_NUMBER,
        value=value,
        raw_quote=value,
        transcript_segment_ids=[segment.id],
        extractor=EXTRACTOR_NAME,
        extractor_version=EXTRACTOR_VERSION,
        confidence=E164_CONFIDENCE,
        status=FindingStatus.PROPOSED,
        created_at=segment.created_at,
    )


def _finding_id(call_session_id: UUID, segment_id: UUID, value: str) -> UUID:
    return uuid5(
        SWITCHBOARD_ID_NAMESPACE,
        f"intelligence_finding|{call_session_id}|{segment_id}|{value}",
    )
