"""In-process provider used by the local simulator. No carrier account required."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from switchboard.errors import ProviderPayloadError
from switchboard.ids import new_id
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

_MOCK_PROTOCOL = "switchboard.media.v1"


class MockInboundPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    from_number: str = Field(validation_alias="from")
    to_number: str = Field(validation_alias="to")
    provider_call_id: str | None = None
    direction: Literal["inbound", "outbound"] = "inbound"

    @field_validator("from_number", "to_number")
    @classmethod
    def _required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("phone number is required")
        return stripped


class MockStatusPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider_call_id: str
    status: str
    reason: str = ""


class MockTelephonyProvider(TelephonyProvider):
    """JSON webhooks and the switchboard.media.v1 websocket protocol."""

    name = "mock"

    async def receive_call(self, request: ProviderWebhookRequest) -> NormalizedInbound:
        payload = _read_model(request, "application/json", MockInboundPayload)
        provider_call_id = payload.provider_call_id or new_id("mock_")
        return NormalizedInbound(
            provider=self.name,
            provider_call_id=provider_call_id,
            from_number=payload.from_number,
            to_number=payload.to_number,
            direction=payload.direction,
            provider_metadata={"direction": payload.direction},
        )

    def build_answer(self, session: CallSession, media_ws_url: str) -> ProviderHttpResponse:
        require_websocket_url(media_ws_url)
        body = {
            "call_id": session.call_id,
            "provider_call_id": session.provider_call_id,
            "state": session.state.value,
            "media_stream_url": f"{media_ws_url}?call_id={session.call_id}",
        }
        return ProviderHttpResponse(
            status_code=200,
            media_type="application/json",
            body=json.dumps(body).encode("utf-8"),
        )

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
            protocol=_MOCK_PROTOCOL,
            encoding=encoding,
            sample_rate=sample_rate,
        )

    async def forward_call(self, session: CallSession, destination: str) -> None:
        del session, destination

    async def terminate_call(self, session: CallSession, reason: str) -> None:
        del session, reason

    async def get_call_status(self, session: CallSession) -> ProviderCallStatus:
        return local_call_status(session)

    async def parse_status_callback(self, request: ProviderWebhookRequest) -> StatusUpdate:
        payload = _read_model(request, "application/json", MockStatusPayload)
        category = _status_category(payload.status)
        reason = payload.reason or payload.status
        return StatusUpdate(
            provider_call_id=payload.provider_call_id,
            category=category,
            reason=reason,
            raw_status=payload.status,
        )


def _read_model[T: BaseModel](request: ProviderWebhookRequest, expected: str, model: type[T]) -> T:
    if media_type_of(request.content_type) != expected:
        raise ProviderPayloadError(f"mock provider expects {expected}")
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ProviderPayloadError("mock webhook body is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ProviderPayloadError("mock webhook body must be a JSON object")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ProviderPayloadError("mock webhook body is missing required fields") from exc


def _status_category(raw_status: str) -> StatusCategory:
    normalized = raw_status.strip().lower().replace("_", "-")
    if normalized in {"completed", "complete"}:
        return StatusCategory.COMPLETED
    if normalized in {"failed", "busy", "no-answer", "canceled", "cancelled"}:
        return StatusCategory.FAILED
    if normalized in {"ringing", "in-progress", "queued", "initiated"}:
        return StatusCategory.IGNORE
    raise ProviderPayloadError(f"unsupported mock call status: {raw_status}")

