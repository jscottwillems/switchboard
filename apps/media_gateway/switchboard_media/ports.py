"""STT and TTS ports. Owner: ECHO.

Mock STT maps one fixture frame to one final segment (SB-005).
Mock TTS returns one local PCMU frame.
"""

import hashlib
from typing import Protocol

from pydantic import Field

from switchboard_schemas.common import Confidence, ContractModel

from switchboard_media.protocol import (
    TELEPHONY_DEFAULT_ENCODING,
    TELEPHONY_DEFAULT_SAMPLE_RATE_HZ,
)

MOCK_TTS_ENCODING = TELEPHONY_DEFAULT_ENCODING
MOCK_TTS_SAMPLE_RATE_HZ = TELEPHONY_DEFAULT_SAMPLE_RATE_HZ
MOCK_TTS_FRAME_MS = 20
MOCK_TTS_FRAME_BYTES = MOCK_TTS_SAMPLE_RATE_HZ * MOCK_TTS_FRAME_MS // 1000

# One 20 ms PCMU frame of 0xFF. The mock does not decode it.
# Any other payload, including a shorter run of 0xFF, returns no transcript.
MOCK_STT_FIXTURE_FRAME = b"\xff" * MOCK_TTS_FRAME_BYTES
MOCK_STT_FINAL_TEXT = "fixture caller segment"
MOCK_STT_CONFIDENCE = 1.0
MOCK_STT_START_OFFSET_MS = 0
MOCK_STT_END_OFFSET_MS = MOCK_TTS_FRAME_MS


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
    """Offline exact-match recognizer. No network and no account.

    `MOCK_STT_FIXTURE_FRAME` returns one final segment. Every other payload
    returns `[]`, so arbitrary audio does not become a transcript.
    `stt_confidence` is the provider score for that exact match.
    """

    def push_audio(self, payload: bytes) -> list[SttEvent]:
        if payload != MOCK_STT_FIXTURE_FRAME:
            return []
        return [
            SttEvent(
                text=MOCK_STT_FINAL_TEXT,
                is_final=True,
                stt_confidence=MOCK_STT_CONFIDENCE,
                start_offset_ms=MOCK_STT_START_OFFSET_MS,
                end_offset_ms=MOCK_STT_END_OFFSET_MS,
            )
        ]


class MockTts:
    """Offline `audio/pcmu` at 8 kHz mono. No network and no account.

    Empty text returns `b""`. Any other string returns one 20 ms frame (160 bytes).
    The bytes are SHA-256 of the UTF-8 text, repeated to the frame length.
    """

    def synthesize(self, text: str) -> bytes:
        if text == "":
            return b""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeats = (MOCK_TTS_FRAME_BYTES + len(digest) - 1) // len(digest)
        return (digest * repeats)[:MOCK_TTS_FRAME_BYTES]
