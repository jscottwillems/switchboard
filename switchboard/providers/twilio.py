"""Twilio programmable voice adapter.

This adapter does not import the Twilio SDK. It speaks the webhook, TwiML,
Media Streams, and Calls REST shapes directly so business logic stays on
TelephonyProvider.
"""

import logging
from typing import Protocol
from xml.sax.saxutils import escape

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from switchboard.config import Settings
from switchboard.errors import ProviderConfigurationError, ProviderError, ProviderPayloadError
from switchboard.models.session import (
    CallSession,
    MediaStreamHandle,
    NormalizedInbound,
    ProviderCallStatus,
    StatusCategory,
    StatusUpdate,
)
from switchboard.providers.base import (
    ProviderHttpResponse,
    ProviderWebhookRequest,
    TelephonyProvider,
    local_call_status,
    media_type_of,
    require_websocket_url,
)
from switchboard.security.signatures import parse_form_body

logger = logging.getLogger(__name__)

_TWILIO_PROTOCOL = "twilio.media.v1"
_TWILIO_METADATA_KEYS = (
    "AccountSid",
    "CallStatus",
    "Direction",
    "CallerName",
    "FromCity",
    "FromState",
    "FromZip",
    "FromCountry",
    "ToCity",
    "ToState",
    "ToZip",
    "ToCountry",
)


class TwilioTransport(Protocol):
    async def update_call(
        self,
        *,
        account_sid: str,
        auth_token: str,
        call_sid: str,
        data: dict[str, str],
    ) -> None:
        """POST a Calls resource update."""


class HttpxTwilioTransport:
    """Production transport. Tests inject a recorder instead."""

    async def update_call(
        self,
        *,
        account_sid: str,
        auth_token: str,
        call_sid: str,
        data: dict[str, str],
    ) -> None:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_sid}.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data, auth=(account_sid, auth_token))
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"twilio call update failed: {type(exc).__name__}") from exc


class _TwilioVoiceForm(BaseModel):
    model_config = ConfigDict(extra="ignore")

    CallSid: str
    From: str
    To: str
    Direction: str = "inbound"
    CallStatus: str | None = None
    AccountSid: str | None = None


class _TwilioStatusForm(BaseModel):
    model_config = ConfigDict(extra="ignore")

    CallSid: str
    CallStatus: str


class TwilioTelephonyProvider(TelephonyProvider):
    """Twilio voice webhooks, TwiML Connect/Stream, and Calls REST updates."""

    name = "twilio"

    def __init__(self, settings: Settings, transport: TwilioTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport if transport is not None else HttpxTwilioTransport()

    async def receive_call(self, request: ProviderWebhookRequest) -> NormalizedInbound:
        form = _read_form(request, _TwilioVoiceForm)
        if not form.From.strip() or not form.To.strip():
            raise ProviderPayloadError("twilio From and To are required")
        return NormalizedInbound(
            provider=self.name,
            provider_call_id=form.CallSid,
            from_number=form.From.strip(),
            to_number=form.To.strip(),
            direction=_direction(form.Direction),
            provider_metadata=_metadata(request),
        )

    def build_answer(self, session: CallSession, media_ws_url: str) -> ProviderHttpResponse:
        del session
        require_websocket_url(media_ws_url)
        safe_url = escape(media_ws_url, {'"': "&quot;"})
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Connect><Stream url=\"{safe_url}\"/></Connect></Response>"
        )
        return ProviderHttpResponse(status_code=200, media_type="text/xml", body=xml.encode("utf-8"))

    async def open_media_stream(
        self,
        session: CallSession,
        stream_id: str,
        *,
        encoding: str,
        sample_rate: int,
    ) -> MediaStreamHandle:
        return MediaStreamHandle(
            stream_id=stream_id,
            call_id=session.call_id,
            protocol=_TWILIO_PROTOCOL,
            encoding=encoding,
            sample_rate=sample_rate,
        )

    async def forward_call(self, session: CallSession, destination: str) -> None:
        self._require_credentials()
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Dial>{escape(destination)}</Dial></Response>"
        )
        await self._transport.update_call(
            account_sid=self._settings.twilio_account_sid,
            auth_token=self._settings.twilio_auth_token,
            call_sid=session.provider_call_id,
            data={"Twiml": twiml},
        )

    async def terminate_call(self, session: CallSession, reason: str) -> None:
        if not self._credentials_present():
            logger.info(
                "twilio terminate skipped",
                extra={"telemetry": {"name": "provider.side_effect", "performed": False, "reason": reason}},
            )
            return
        await self._transport.update_call(
            account_sid=self._settings.twilio_account_sid,
            auth_token=self._settings.twilio_auth_token,
            call_sid=session.provider_call_id,
            data={"Status": "completed"},
        )

    async def get_call_status(self, session: CallSession) -> ProviderCallStatus:
        return local_call_status(session)

    async def parse_status_callback(self, request: ProviderWebhookRequest) -> StatusUpdate:
        form = _read_form(request, _TwilioStatusForm)
        category = _status_category(form.CallStatus)
        return StatusUpdate(
            provider_call_id=form.CallSid,
            category=category,
            reason=form.CallStatus,
            raw_status=form.CallStatus,
        )

    def _credentials_present(self) -> bool:
        return bool(self._settings.twilio_account_sid and self._settings.twilio_auth_token)

    def _require_credentials(self) -> None:
        if not self._credentials_present():
            raise ProviderConfigurationError(
                "SWITCHBOARD_TWILIO_ACCOUNT_SID and SWITCHBOARD_TWILIO_AUTH_TOKEN are required to forward calls"
            )


def _read_form[T: BaseModel](request: ProviderWebhookRequest, model: type[T]) -> T:
    if media_type_of(request.content_type) != "application/x-www-form-urlencoded":
        raise ProviderPayloadError("twilio provider expects application/x-www-form-urlencoded")
    try:
        parsed = parse_form_body(request.body)
        return model.model_validate(parsed)
    except (UnicodeDecodeError, ValidationError) as exc:
        raise ProviderPayloadError("twilio webhook body is missing required fields") from exc


def _direction(raw: str) -> str:
    lowered = raw.lower()
    if lowered.startswith("outbound"):
        return "outbound"
    return "inbound"


def _metadata(request: ProviderWebhookRequest) -> dict[str, str]:
    parsed = parse_form_body(request.body)
    metadata: dict[str, str] = {}
    for key in _TWILIO_METADATA_KEYS:
        value = parsed.get(key)
        if value:
            metadata[key] = value[:256]
    return metadata


def _status_category(raw_status: str) -> StatusCategory:
    normalized = raw_status.strip().lower()
    if normalized == "completed":
        return StatusCategory.COMPLETED
    if normalized in {"failed", "busy", "no-answer", "canceled"}:
        return StatusCategory.FAILED
    if normalized in {"queued", "ringing", "in-progress", "initiated"}:
        return StatusCategory.IGNORE
    raise ProviderPayloadError(f"unsupported twilio call status: {raw_status}")
