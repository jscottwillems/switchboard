"""Carrier webhooks. Voice persistence writes Atlas obs tables."""

import json
from typing import Any, Never
from uuid import UUID, uuid5

from fastapi import APIRouter, Request
from pydantic import ValidationError

from switchboard_observability import log_info
from switchboard_schemas.api import (
    MockStatusWebhook,
    MockVoiceWebhook,
    StatusAccepted,
    TelephonyWebhookAck,
    VoiceInstruction,
)
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import CallState, CarrierProvider
from switchboard_schemas.observations import CallSession
from switchboard_telephony import (
    InstructionRenderer,
    MockSignatureVerifier,
    VoiceAction,
    VoiceInstructionRenderer,
)

from switchboard_api.errors import ApiError
from switchboard_api.memory_tokens import issue_token
from switchboard_api.obs_store import get_obs_store
from switchboard_api.settings import get_settings
from switchboard_api.telephony_events import publish_envelope, telephony_call_received_envelope
from switchboard_api.webhook_edge import admit_webhook, status_for

router = APIRouter(prefix="/v1/telephony", tags=["telephony"])
_verifier = MockSignatureVerifier()
_renderer: InstructionRenderer = VoiceInstructionRenderer()
VOICE_RECEIPT_EVENT = "voice"


def signature_status(raw_body: bytes, headers: list[tuple[str, str]]) -> bool | None:
    """True or False from the verifier. None when the dev bypass skips the check."""

    settings = get_settings()
    lowered = {key.lower(): value for key, value in headers}
    if settings.env == "dev" and settings.dev_webhook_bypass:
        return None
    return _verifier.verify(raw_body, lowered)


def webhook_authorized(raw_body: bytes, headers: list[tuple[str, str]]) -> bool:
    return signature_status(raw_body, headers) is not False


def session_id_for(provider: CarrierProvider, provider_call_id: str) -> UUID:
    return uuid5(SWITCHBOARD_ID_NAMESPACE, f"{provider.value}:{provider_call_id}")


def render_instruction(
    action: VoiceAction,
    *,
    stream_url: str | None = None,
    stream_token: str | None = None,
) -> VoiceInstruction:
    """API entry for carrier instructions. Every action goes through the telephony renderer."""

    match action:
        case "connect_stream":
            return _renderer.render(
                "connect_stream",
                stream_url=stream_url,
                stream_token=stream_token,
            )
        case "hangup":
            return _renderer.render("hangup", stream_url=stream_url, stream_token=stream_token)
        case "reject":
            return _renderer.render("reject", stream_url=stream_url, stream_token=stream_token)
        case unreachable:
            return _never(unreachable)


def _never(value: Never) -> Never:
    raise AssertionError(f"unhandled voice action: {value}")


def _json_object(raw: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _ringing_session(
    provider: CarrierProvider,
    body: MockVoiceWebhook,
    operator_number_id: UUID,
) -> CallSession:
    return CallSession(
        id=session_id_for(provider, body.provider_call_id),
        operator_number_id=operator_number_id,
        external_call_id=body.provider_call_id,
        carrier=provider.value,
        caller_number_e164=body.from_e164,
        called_number_e164=body.to_e164,
        state=CallState.RINGING,
        started_at=body.timestamp,
    )


async def _admitted_body(request: Request, provider: CarrierProvider, route: str) -> bytes:
    """Size and rate limits, then the raw body. Signature and schema stay with the caller."""

    raw = await request.body()
    denied = admit_webhook(request, raw)
    if denied is not None:
        status_code, error, message = status_for(denied)
        log_info("webhook_rejected", provider=provider.value, route=route, reason=error)
        raise ApiError(status_code, error, message)
    return raw


def _parse_voice(raw: bytes) -> MockVoiceWebhook:
    try:
        return MockVoiceWebhook.model_validate_json(raw)
    except (ValidationError, UnicodeError):
        raise ApiError(422, "invalid_request", "Request failed validation.") from None


def _parse_status(raw: bytes) -> MockStatusWebhook:
    try:
        return MockStatusWebhook.model_validate_json(raw)
    except (ValidationError, UnicodeError):
        raise ApiError(422, "invalid_request", "Request failed validation.") from None


@router.post("/voice/{provider}", response_model=TelephonyWebhookAck)
async def inbound_voice(provider: CarrierProvider, request: Request) -> TelephonyWebhookAck:
    raw = await _admitted_body(request, provider, "voice")
    headers = list(request.headers.items())
    checked = signature_status(raw, headers)
    payload = _json_object(raw)
    if checked is False:
        if payload is not None:
            _store_receipt(
                provider=provider.value,
                payload=payload,
                signature_valid=False,
                call_session_id=None,
            )
        log_info(
            "webhook_rejected",
            provider=provider.value,
            route="voice",
            error="webhook_unauthorized",
        )
        raise ApiError(401, "webhook_unauthorized", "Webhook signature was rejected.")
    if payload is None:
        raise ApiError(422, "invalid_request", "Request failed validation.")
    body = _parse_voice(raw)

    session_id, created = _open_session_or_reject(provider, body, payload, checked)
    if created:
        publish_envelope(
            telephony_call_received_envelope(
                call_session_id=session_id,
                external_call_id=body.provider_call_id,
                carrier=provider.value,
                caller_number_e164=body.from_e164,
                called_number_e164=body.to_e164,
                occurred_at=body.timestamp,
            )
        )
    issued = issue_token(session_id)
    log_info("webhook_accepted", provider=provider.value, route="voice")
    return TelephonyWebhookAck(
        call_session_id=session_id,
        instruction=render_instruction(
            "connect_stream",
            stream_url=issued.stream_url,
            stream_token=issued.token,
        ),
    )


def _open_session_or_reject(
    provider: CarrierProvider,
    body: MockVoiceWebhook,
    payload: dict[str, Any],
    signature_valid: bool | None,
) -> tuple[UUID, bool]:
    store = get_obs_store()
    session_id: UUID | None = None
    created = False
    with store.connection() as conn:
        operator_id = store.find_active_operator_id(conn, body.to_e164)
        if operator_id is None:
            store.insert_webhook_receipt(
                conn,
                provider=provider.value,
                event_type=VOICE_RECEIPT_EVENT,
                payload=payload,
                signature_valid=signature_valid,
                call_session_id=None,
            )
        else:
            session_id, created = store.insert_ringing_session(
                conn,
                _ringing_session(provider, body, operator_id),
            )
            store.insert_webhook_receipt(
                conn,
                provider=provider.value,
                event_type=VOICE_RECEIPT_EVENT,
                payload=payload,
                signature_valid=signature_valid,
                call_session_id=session_id,
            )
    if session_id is None:
        log_info(
            "webhook_rejected",
            provider=provider.value,
            route="voice",
            error="number_not_enrolled",
        )
        raise ApiError(
            403,
            "number_not_enrolled",
            "Called number is not an active operator number.",
        )
    return session_id, created


def _store_receipt(
    *,
    provider: str,
    payload: dict[str, Any],
    signature_valid: bool | None,
    call_session_id: UUID | None,
) -> None:
    store = get_obs_store()
    with store.connection() as conn:
        store.insert_webhook_receipt(
            conn,
            provider=provider,
            event_type=VOICE_RECEIPT_EVENT,
            payload=payload,
            signature_valid=signature_valid,
            call_session_id=call_session_id,
        )


@router.post("/status/{provider}", response_model=StatusAccepted)
async def status_callback(provider: CarrierProvider, request: Request) -> StatusAccepted:
    raw = await _admitted_body(request, provider, "status")
    if not webhook_authorized(raw, list(request.headers.items())):
        log_info("webhook_rejected", provider=provider.value, route="status", error="webhook_unauthorized")
        raise ApiError(401, "webhook_unauthorized", "Webhook signature was rejected.")
    _parse_status(raw)
    log_info("webhook_accepted", provider=provider.value, route="status")
    return StatusAccepted()
