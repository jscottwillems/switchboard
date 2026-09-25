"""Local control reads and actions. Unauthenticated in this slice."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from switchboard.api.deps import get_container
from switchboard.container import Container
from switchboard.models.events import CallEvent
from switchboard.models.media import RawObservation
from switchboard.models.session import CallSession, ProviderCallStatus

router = APIRouter(prefix="/calls", tags=["calls"])


class CallDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: CallSession
    observations: list[RawObservation]
    events: list[CallEvent]


class ForwardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=2)


class TerminateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = "operator"


@router.get("/{call_id}", response_model=CallDetail)
async def get_call(call_id: str, container: Container = Depends(get_container)) -> CallDetail:
    session = await container.lifecycle.get_session(call_id)
    observations = await container.lifecycle.list_observations(call_id)
    events = await container.lifecycle.list_events(call_id)
    return CallDetail(session=session, observations=observations, events=events)


@router.get("/{call_id}/events", response_model=list[CallEvent])
async def list_events(call_id: str, container: Container = Depends(get_container)) -> list[CallEvent]:
    return await container.lifecycle.list_events(call_id)


@router.get("/{call_id}/status", response_model=ProviderCallStatus)
async def get_status(call_id: str, container: Container = Depends(get_container)) -> ProviderCallStatus:
    return await container.lifecycle.get_status(call_id)


@router.post("/{call_id}/forward", response_model=CallSession)
async def forward_call(
    call_id: str,
    payload: ForwardRequest,
    container: Container = Depends(get_container),
) -> CallSession:
    return await container.lifecycle.forward(call_id, payload.destination)


@router.post("/{call_id}/terminate", response_model=CallSession)
async def terminate_call(
    call_id: str,
    payload: TerminateRequest,
    container: Container = Depends(get_container),
) -> CallSession:
    return await container.lifecycle.hangup(call_id, payload.reason)
