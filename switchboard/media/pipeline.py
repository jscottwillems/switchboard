"""Media reply port.

ECHO implements this protocol next. BELL ships a fixed tone so the websocket
path is testable without speech recognition or synthesis.
"""

from typing import Protocol

from switchboard.media.audio import fixed_response_frame
from switchboard.models.media import InboundMediaPacket, OutboundAudioFrame


class MediaPipeline(Protocol):
    async def handle_inbound(self, call_id: str, packet: InboundMediaPacket) -> OutboundAudioFrame | None:
        """Return the next provider-wire frame, or None to send no audio.

        ``packet.payload`` is μ-law, 8 kHz, mono. The return value must be the
        same wire format. PCM16 at 16 kHz is an ECHO-internal normalize target
        and must be converted before it is returned here. Implementations must
        not assume a vendor websocket frame. Returning None means the gateway
        stays quiet for this packet.
        """


class FixedToneMediaPipeline:
    """Reply to every inbound packet with the same known tone frame."""

    async def handle_inbound(self, call_id: str, packet: InboundMediaPacket) -> OutboundAudioFrame | None:
        del call_id, packet
        return OutboundAudioFrame(payload=fixed_response_frame(), source="fixed_response")
