"""Media reply port.

ECHO implements this protocol next. BELL ships a fixed tone so the websocket
path is testable without speech recognition or synthesis.
"""

from typing import Protocol

from switchboard.media.audio import fixed_response_frame
from switchboard.models.media import InboundMediaPacket, OutboundAudioFrame


class MediaPipeline(Protocol):
    async def handle_inbound(self, call_id: str, packet: InboundMediaPacket) -> OutboundAudioFrame | None:
        """Return the next 8 kHz μ-law frame, or None to send no audio.

        ``packet`` is a normalized observation. Implementations must not assume
        a vendor websocket frame. Returning None means the gateway stays quiet
        for this packet.
        """


class FixedToneMediaPipeline:
    """Reply to every inbound packet with the same known tone frame."""

    async def handle_inbound(self, call_id: str, packet: InboundMediaPacket) -> OutboundAudioFrame | None:
        del call_id, packet
        return OutboundAudioFrame(payload=fixed_response_frame(), source="fixed_response")
