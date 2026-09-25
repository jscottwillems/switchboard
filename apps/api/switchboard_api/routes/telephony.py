"""Carrier webhooks. Persistence is intentionally absent; see docs/STATUS.md."""

from uuid import UUID, uuid5

from fastapi import APIRouter, Request

from switchboard_schemas.api import (
    MockStatusWebhook,
    MockVoiceWebhook,
    StatusAccepted,
    TelephonyWebhookAck,
    VoiceInstruction,
)
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import CarrierProvider
from switchboard_telephony import MockSignatureVerifier

from switchboard_api.errors import ApiError
from switchboard_api.memory_tokens import issue_token
from switchboard_api.settings import get_settings
from switchboard_observability import log_info

router = APIRouter(prefix="/v1/telephony", tags=["telephony"])
_verifier = MockSignatureVerifier()


def webhook_authorized(raw_body: bytes, headers: list[tuple[str, str]]) -> bool:
    settings = get_settings()
    lowered = {key.lower(): value for key, value in headers}
    bypass_honored = settings.env == "dev" and settings.dev_webhook_bypass
    if bypass_honored:
        return True
    return _verifier.verify(raw_body, lowered)


def session_id_for(provider: CarrierProvider, provider_call_id: str) -> UUID:
    return uuid5(SWITCHBOARD_ID_NAMESPACE, f"{provider.value}:{provider_call_id}")


@router.post("/voice/{provider}", response_model=TelephonyWebhookAck)
async def inbound_voice(
    provider: CarrierProvider,
    body: MockVoiceWebhook,
    request: Request,
) -> TelephonyWebhookAck:
    raw = await request.body()
    if not webhook_authorized(raw, list(request.headers.items())):
        log_info("webhook_rejected", provider=provider.value, route="voice")
        raise ApiError(401, "webhook_unauthorized", "Webhook signature was rejected.")
    call_session_id = session_id_for(provider, body.provider_call_id)
    issued = issue_token(call_session_id)
    log_info("webhook_accepted", provider=provider.value, route="voice")
    return TelephonyWebhookAck(
        call_session_id=call_session_id,
        instruction=VoiceInstruction(
            action="connect_stream",
            stream_url=issued.stream_url,
            stream_token=issued.token,
        ),
    )


@router.post("/status/{provider}", response_model=StatusAccepted)
async def status_callback(
    provider: CarrierProvider,
    body: MockStatusWebhook,
    request: Request,
) -> StatusAccepted:
    del body
    raw = await request.body()
    if not webhook_authorized(raw, list(request.headers.items())):
        log_info("webhook_rejected", provider=provider.value, route="status")
        raise ApiError(401, "webhook_unauthorized", "Webhook signature was rejected.")
    log_info("webhook_accepted", provider=provider.value, route="status")
    return StatusAccepted()
