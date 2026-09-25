"""Render VoiceInstruction values for the carrier boundary.

The HTTP ack keeps stream_url and stream_token apart. append_stream_token is
the only place that builds the carrier query string.
"""

from typing import Literal, Protocol
from urllib.parse import quote

from switchboard_schemas.api import VoiceInstruction

VoiceAction = Literal["connect_stream", "hangup", "reject"]


class InstructionRenderer(Protocol):
    def render(
        self,
        action: VoiceAction,
        *,
        stream_url: str | None = None,
        stream_token: str | None = None,
    ) -> VoiceInstruction:
        """Return a VoiceInstruction whose stream fields match the action."""


class VoiceInstructionRenderer:
    """Builds connect_stream, hangup, and reject instructions."""

    def render(
        self,
        action: VoiceAction,
        *,
        stream_url: str | None = None,
        stream_token: str | None = None,
    ) -> VoiceInstruction:
        if stream_url and stream_token and _token_embedded(stream_url, stream_token):
            raise ValueError("stream token must not be embedded in stream_url")
        return VoiceInstruction(
            action=action,
            stream_url=stream_url,
            stream_token=stream_token,
        )


def append_stream_token(instruction: VoiceInstruction) -> str:
    """Carrier media URL. The instruction body itself never contains the query."""

    if instruction.action != "connect_stream":
        raise ValueError("stream token is only appended for connect_stream")
    if not instruction.stream_url or not instruction.stream_token:
        raise ValueError("connect_stream requires stream_url and stream_token")
    if _token_embedded(instruction.stream_url, instruction.stream_token):
        raise ValueError("stream token must not be embedded in stream_url")
    separator = "&" if "?" in instruction.stream_url else "?"
    token = quote(instruction.stream_token, safe="")
    return f"{instruction.stream_url}{separator}token={token}"


def _token_embedded(stream_url: str, stream_token: str) -> bool:
    if "token=" in stream_url:
        return True
    return stream_token in stream_url
