"""Local transcript adapter.

This is the minimum shape Sherlock needs in order to anchor an observation
to a spoken span. It is not a shared Switchboard call-session contract.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from switchboard_intelligence.schemas.common import CallRelativeSeconds


class SpeakerRole(str, Enum):
    SCAMMER = "scammer"
    TARGET = "target"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=1)
    speaker: SpeakerRole
    text: str = Field(min_length=1)
    start_timestamp: CallRelativeSeconds
    end_timestamp: CallRelativeSeconds

    @model_validator(mode="after")
    def timestamps_are_ordered(self) -> "TranscriptSegment":
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("end_timestamp must be greater than or equal to start_timestamp")
        return self


class Transcript(BaseModel):
    """One call's segments. `call_id` is an opaque string supplied by the caller."""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(min_length=1)
    segments: list[TranscriptSegment] = Field(min_length=1)

    @model_validator(mode="after")
    def segment_ids_are_unique(self) -> "Transcript":
        segment_ids = [segment.segment_id for segment in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("segment_id values must be unique within a transcript")
        return self
