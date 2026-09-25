"""Carrier webhooks. Voice and status persistence write Atlas obs tables."""

import json
from datetime import datetime
from typing import Any, Never
from uuid import UUID, uuid5

from fastapi import APIRouter, Request
from pydantic import ValidationError

from switchboard_observability import log_info
from switchboard_repositories import NotFound, StateConflict
from switchboard_schemas.api import (
    MockStatusWebhook,
    MockVoiceWebhook,
    StatusAccepted,
    TelephonyWebhookAck,
    VoiceInstruction,
)
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import CallState, CarrierProvider
from switchboard_schemas.events import EventEnvelope
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
from switchboard_api.telephony_events import (
    publish_envelope,
    telephony_call_answered_envelope,
    telephony_call_completed_envelope,
    telephony_call_failed_envelope,
    telephony_call_received_envelope,
)
from switchboard_api.webhook_edge import admit_webhook, status_for

router = APIRouter(prefix="/v1/telephony", tags=["telephony"])
_verifier = MockSignatureVerifier()
_renderer: InstructionRenderer = VoiceInstructionRenderer()
VOICE_RECEIPT_EVENT = "voice"
STATUS_RECEIPT_EVENT = "status"
_FAILED_END_REASON = "failed"


def signature_status(raw_body: bytes, headers: list[tuple[str, str]]) -> bool | None:
    """True or False from the verifier. None when the dev bypass skips the check."""

    settings = get_settings()
    lowered = {key.lower(): value for key, value in headers}
    if settings.env == "dev" and settings.dev_webhook_bypass:
        return None
    return _verifier.verify(raw_body, lowered)


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
                event_type=VOICE_RECEIPT_EVENT,
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
    event_type: str,
    payload: dict[str, Any],
    signature_valid: bool | None,
    call_session_id: UUID | None,
) -> None:
    store = get_obs_store()
    with store.connection() as conn:
        store.insert_webhook_receipt(
            conn,
            provider=provider,
            event_type=event_type,
            payload=payload,
            signature_valid=signature_valid,
            call_session_id=call_session_id,
        )


def _publishes_status(status: CallState) -> bool:
    match status:
        case CallState.IN_PROGRESS | CallState.COMPLETED | CallState.FAILED:
            return True
        case CallState.RINGING:
            return False
        case unreachable:
            return _never(unreachable)


def _failed_reason(end_reason: str | None) -> str:
    if end_reason is None or end_reason.strip() == "":
        return _FAILED_END_REASON
    return end_reason


def _status_timestamps(body: MockStatusWebhook) -> tuple[datetime | None, datetime | None]:
    """Return answered_at and ended_at for this callback. Ringing changes neither."""

    match body.status:
        case CallState.IN_PROGRESS:
            return body.timestamp, None
        case CallState.COMPLETED | CallState.FAILED:
            return None, body.timestamp
        case CallState.RINGING:
            return None, None
        case unreachable:
            return _never(unreachable)


def _stored_end_reason(body: MockStatusWebhook) -> str | None:
    match body.status:
        case CallState.FAILED:
            return _failed_reason(body.end_reason)
        case CallState.COMPLETED:
            return body.end_reason
        case CallState.IN_PROGRESS | CallState.RINGING:
            return None
        case unreachable:
            return _never(unreachable)


def _status_occurred_at(session: CallSession, body: MockStatusWebhook) -> datetime:
    match body.status:
        case CallState.IN_PROGRESS:
            when = session.answered_at
        case CallState.COMPLETED | CallState.FAILED:
            when = session.ended_at
        case CallState.RINGING:
            when = body.timestamp
        case unreachable:
            return _never(unreachable)
    return when if when is not None else body.timestamp


def _status_envelope(session: CallSession, body: MockStatusWebhook) -> EventEnvelope:
    occurred_at = _status_occurred_at(session, body)
    match body.status:
        case CallState.IN_PROGRESS:
            return telephony_call_answered_envelope(
                call_session_id=session.id,
                external_call_id=session.external_call_id,
                occurred_at=occurred_at,
            )
        case CallState.COMPLETED:
            return telephony_call_completed_envelope(
                call_session_id=session.id,
                external_call_id=session.external_call_id,
                occurred_at=occurred_at,
                end_reason=session.end_reason,
            )
        case CallState.FAILED:
            return telephony_call_failed_envelope(
                call_session_id=session.id,
                external_call_id=session.external_call_id,
                occurred_at=occurred_at,
                end_reason=_failed_reason(session.end_reason),
            )
        case CallState.RINGING:
            raise AssertionError("ringing status does not publish a telephony event")
        case unreachable:
            return _never(unreachable)


def _apply_status_callback(
    provider: CarrierProvider,
    body: MockStatusWebhook,
    payload: dict[str, Any],
    signature_valid: bool | None,
) -> EventEnvelope | None:
    """Commit the receipt and any forward transition. Publish happens after return."""

    store = get_obs_store()
    missing = False
    conflict = False
    envelope: EventEnvelope | None = None
    answered_at, ended_at = _status_timestamps(body)
    with store.connection() as conn:
        current = store.get_call_session(conn, provider.value, body.provider_call_id)
        if current is None:
            store.insert_webhook_receipt(
                conn,
                provider=provider.value,
                event_type=STATUS_RECEIPT_EVENT,
                payload=payload,
                signature_valid=signature_valid,
                call_session_id=None,
            )
            missing = True
        else:
            store.insert_webhook_receipt(
                conn,
                provider=provider.value,
                event_type=STATUS_RECEIPT_EVENT,
                payload=payload,
                signature_valid=signature_valid,
                call_session_id=current.id,
            )
            session = current
            if current.state != body.status:
                try:
                    session = store.apply_call_state(
                        conn,
                        current.id,
                        state=body.status,
                        answered_at=answered_at,
                        ended_at=ended_at,
                        end_reason=_stored_end_reason(body),
                    )
                except StateConflict:
                    conflict = True
                except NotFound:
                    missing = True
            if not missing and not conflict and _publishes_status(body.status):
                envelope = _status_envelope(session, body)
    if missing:
        log_info(
            "webhook_rejected",
            provider=provider.value,
            route="status",
            error="call_not_found",
        )
        raise ApiError(404, "call_not_found", "No call session exists with that id.")
    if conflict:
        log_info(
            "webhook_rejected",
            provider=provider.value,
            route="status",
            error="state_conflict",
        )
        raise ApiError(409, "state_conflict", "Call session cannot move to that state.")
    return envelope


@router.post("/status/{provider}", response_model=StatusAccepted)
async def status_callback(provider: CarrierProvider, request: Request) -> StatusAccepted:
    raw = await _admitted_body(request, provider, "status")
    headers = list(request.headers.items())
    checked = signature_status(raw, headers)
    payload = _json_object(raw)
    if checked is False:
        if payload is not None:
            _store_receipt(
                provider=provider.value,
                event_type=STATUS_RECEIPT_EVENT,
                payload=payload,
                signature_valid=False,
                call_session_id=None,
            )
        log_info(
            "webhook_rejected",
            provider=provider.value,
            route="status",
            error="webhook_unauthorized",
        )
        raise ApiError(401, "webhook_unauthorized", "Webhook signature was rejected.")
    if payload is None:
        raise ApiError(422, "invalid_request", "Request failed validation.")
    body = _parse_status(raw)
    envelope = _apply_status_callback(provider, body, payload, checked)
    if envelope is not None:
        publish_envelope(envelope)
    log_info("webhook_accepted", provider=provider.value, route="status")
    return StatusAccepted()
