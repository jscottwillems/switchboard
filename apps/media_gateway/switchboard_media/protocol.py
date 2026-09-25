"""switchboard.media.v1 session: parse frames and buffer outbound audio.

Carrier-native messages are translated before they reach this socket.
Audio bytes are counted for the socket and then dropped. They are not logged.
"""

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, assert_never
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from switchboard_schemas.media import (
    InboundMediaMessage,
    StreamClear,
    StreamMedia,
    StreamStart,
    StreamStop,
)

CLOSE_NORMAL = 1000
CLOSE_INVALID_PAYLOAD = 1007
CLOSE_POLICY_VIOLATION = 1008

# MVP telephony default. BELL translates carrier audio to this before the socket.
TELEPHONY_DEFAULT_ENCODING: Literal["audio/pcmu"] = "audio/pcmu"
TELEPHONY_DEFAULT_SAMPLE_RATE_HZ = 8000
TELEPHONY_DEFAULT_CHANNELS = 1

FrameReason = Literal[
    "invalid_message",
    "start_required",
    "already_started",
    "already_stopped",
    "invalid_audio",
    "session_mismatch",
    "empty_frame",
]

_INBOUND: TypeAdapter[InboundMediaMessage] = TypeAdapter(InboundMediaMessage)


@dataclass(frozen=True)
class AudioFrame:
    sequence: int
    payload: bytes
    source: Literal["json", "binary"]
    timestamp_ms: int | None = None


@dataclass(frozen=True)
class FrameResult:
    audio: AudioFrame | None = None
    close_code: int | None = None
    reason: FrameReason | None = None
    stopped: bool = False


class MediaSession:
    """One accepted socket. `call_session_id` comes from token validation."""

    def __init__(self, call_session_id: UUID) -> None:
        self.call_session_id = call_session_id
        self.started = False
        self.stopped = False
        self.stream_id: str | None = None
        self.encoding: str | None = None
        self.sample_rate_hz: int | None = None
        self.audio_frames = 0
        self._next_sequence = 0
        self._outbound: list[bytes] = []

    def accept_text(self, text: str) -> FrameResult:
        try:
            message = _INBOUND.validate_json(text)
        except ValidationError:
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="invalid_message")
        if isinstance(message, StreamStart):
            return self._start(message)
        if isinstance(message, StreamMedia):
            return self._media(message)
        if isinstance(message, StreamStop):
            return self._stop(message)
        assert_never(message)

    def accept_binary(self, payload: bytes) -> FrameResult:
        """A binary WebSocket frame is audio with an implicit sequence."""

        if self.stopped:
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="already_stopped")
        if not self.started:
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="start_required")
        sequence = self._next_sequence
        self._next_sequence = sequence + 1
        self.audio_frames += 1
        return FrameResult(
            audio=AudioFrame(sequence=sequence, payload=bytes(payload), source="binary")
        )

    def enqueue_outbound(self, audio: bytes) -> None:
        """Queue synthesized audio that has not been written to the carrier yet."""

        if audio:
            self._outbound.append(bytes(audio))

    def pending_outbound_bytes(self) -> int:
        return sum(len(chunk) for chunk in self._outbound)

    def clear_outbound(self) -> StreamClear:
        """Drop queued outbound audio and return the barge-in `clear` message."""

        self._outbound.clear()
        return StreamClear()

    def _start(self, message: StreamStart) -> FrameResult:
        if message.call_session_id != self.call_session_id:
            return FrameResult(close_code=CLOSE_POLICY_VIOLATION, reason="session_mismatch")
        if self.started:
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="already_started")
        self.started = True
        self.stream_id = message.stream_id
        self.encoding = message.media_format.encoding
        self.sample_rate_hz = message.media_format.sample_rate_hz
        return FrameResult()

    def _media(self, message: StreamMedia) -> FrameResult:
        if self.stopped:
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="already_stopped")
        if not self.started:
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="start_required")
        try:
            payload = base64.b64decode(message.payload_b64, validate=True)
        except (ValueError, binascii.Error):
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="invalid_audio")
        self._next_sequence = max(self._next_sequence, message.sequence + 1)
        self.audio_frames += 1
        return FrameResult(
            audio=AudioFrame(
                sequence=message.sequence,
                payload=payload,
                source="json",
                timestamp_ms=message.timestamp_ms,
            )
        )

    def _stop(self, message: StreamStop) -> FrameResult:
        # `reason` is caller-controlled text. Do not log it.
        del message
        if self.stopped:
            return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="already_stopped")
        self.stopped = True
        return FrameResult(stopped=True)


def frame_from_websocket_message(
    session: MediaSession,
    message: Mapping[str, object],
) -> FrameResult:
    """Map one Starlette receive dict onto the media session."""

    payload = message.get("bytes")
    if isinstance(payload, (bytes, bytearray)):
        return session.accept_binary(bytes(payload))
    text = message.get("text")
    if isinstance(text, str):
        return session.accept_text(text)
    return FrameResult(close_code=CLOSE_INVALID_PAYLOAD, reason="empty_frame")
