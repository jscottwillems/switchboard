"""Vendor-neutral telephony port.

FastAPI routes and the call lifecycle depend on this class, not on a vendor
SDK. Concrete adapters translate webhooks and side effects.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from switchboard.errors import ProviderConfigurationError
from switchboard.models.session import (
    CallSession,
    CallState,
    MediaStreamHandle,
    NormalizedInbound,
    ProviderCallStatus,
    StatusUpdate,
)


@dataclass(frozen=True)
class ProviderWebhookRequest:
    body: bytes
    content_type: str


@dataclass(frozen=True)
class ProviderHttpResponse:
    status_code: int
    media_type: str
    body: bytes


class TelephonyProvider(ABC):
    """Programmable-voice operations used by the call lifecycle."""

    name: str

    @abstractmethod
    async def receive_call(self, request: ProviderWebhookRequest) -> NormalizedInbound:
        """Normalize an inbound answer webhook into internal call fields."""

    @abstractmethod
    def build_answer(self, session: CallSession, media_ws_url: str) -> ProviderHttpResponse:
        """Build the carrier response that opens a media stream."""

    @abstractmethod
    async def open_media_stream(self, session: CallSession, stream_id: str, *, encoding: str, sample_rate: int) -> MediaStreamHandle:
        """Register a media stream that the carrier has opened to us."""

    @abstractmethod
    async def forward_call(self, session: CallSession, destination: str) -> None:
        """Ask the carrier to bridge this call to another number."""

    @abstractmethod
    async def terminate_call(self, session: CallSession, reason: str) -> None:
        """Ask the carrier to hang up. Local session state is updated by the lifecycle."""

    @abstractmethod
    async def get_call_status(self, session: CallSession) -> ProviderCallStatus:
        """Return normalized status.

        Slice 1 mirrors the local session. A later slice can refresh from the
        carrier REST API behind the same method.
        """

    @abstractmethod
    async def parse_status_callback(self, request: ProviderWebhookRequest) -> StatusUpdate:
        """Normalize a carrier status callback."""


def media_type_of(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def require_websocket_url(url: str) -> str:
    if not url.startswith(("ws://", "wss://")):
        raise ProviderConfigurationError("media stream URL must start with ws:// or wss://")
    return url


def local_call_status(session: CallSession) -> ProviderCallStatus:
    """Mirror local lifecycle state. Slice 1 does not query the carrier."""

    raw = session.provider_metadata.get("CallStatus") or session.provider_metadata.get("call_status")
    if raw is None and session.state is CallState.FAILED:
        raw = "failed"
    if raw is None and session.state is CallState.COMPLETED:
        raw = "completed"
    return ProviderCallStatus(
        call_id=session.call_id,
        provider=session.provider,
        provider_call_id=session.provider_call_id,
        state=session.state,
        raw_status=raw,
    )
