"""MVP provider-audio wire format.

Team lock from ECHO, not to be changed without ATLAS: the BELL↔provider
media WebSocket carries μ-law, 8 kHz, mono only. PCM16 at 16 kHz is ECHO's
internal normalize target and must not appear on this socket.
"""

from typing import Literal

from switchboard.errors import FrameDecodeError

WIRE_ENCODING: Literal["audio/x-mulaw"] = "audio/x-mulaw"
WIRE_SAMPLE_RATE: Literal[8000] = 8000
WIRE_CHANNELS: Literal[1] = 1


def parse_wire_format(
    *,
    encoding: object = None,
    sample_rate: object = None,
    channels: object = None,
) -> tuple[Literal["audio/x-mulaw"], Literal[8000], Literal[1]]:
    """Accept omitted fields as the MVP default and reject any other declaration."""

    declared_encoding = encoding if isinstance(encoding, str) and encoding else WIRE_ENCODING
    declared_rate = _as_int(sample_rate, WIRE_SAMPLE_RATE)
    declared_channels = _as_int(channels, WIRE_CHANNELS)
    if (
        declared_encoding != WIRE_ENCODING
        or declared_rate != WIRE_SAMPLE_RATE
        or declared_channels != WIRE_CHANNELS
    ):
        raise FrameDecodeError("MVP provider media must be audio/x-mulaw, 8000 Hz, mono")
    return WIRE_ENCODING, WIRE_SAMPLE_RATE, WIRE_CHANNELS


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default
