"""STT and TTS ports. Owner: ECHO. Mocks return no recognition and no audio."""

from typing import Protocol

from pydantic import Field

from switchboard_schemas.common import Confidence, ContractModel


class SttEvent(ContractModel):
    text: str = Field(max_length=8000)
    is_final: bool
    stt_confidence: Confidence | None = None
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(ge=0)


class SttPort(Protocol):
    def push_audio(self, payload: bytes) -> list[SttEvent]:
        """Consume one inbound audio frame. Return zero or more recognition events."""


class TtsPort(Protocol):
    def synthesize(self, text: str) -> bytes:
        """Return encoded audio for the hot path. Empty bytes mean no audio."""


class MockStt:
    def push_audio(self, payload: bytes) -> list[SttEvent]:
        del payload
        return []


class MockTts:
    def synthesize(self, text: str) -> bytes:
        del text
        return b""
