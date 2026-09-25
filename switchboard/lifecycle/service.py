"""Call lifecycle. This module does not import a concrete provider."""

import asyncio
import base64
import hashlib
import re
import time
from typing import Any, Literal, Never

from switchboard.config import Settings
from switchboard.errors import (
    InvalidRequest,
    InvalidTransition,
    NotFoundError,
    ProviderConfigurationError,
    ProviderError,
    ProviderSideEffectError,
)
from switchboard.events.bus import EventBus
from switchboard.ids import new_id
from switchboard.lifecycle.store import InMemorySessionStore
from switchboard.models.events import CallEvent, EventName
from switchboard.models.media import InboundMediaPacket, MediaObservationMeta, RawObservation
from switchboard.models.session import CallSession, CallState, ProviderCallStatus, StatusCategory
from switchboard.models.telemetry import TelemetryRecord
from switchboard.providers.base import ProviderHttpResponse, ProviderWebhookRequest, TelephonyProvider
from switchboard.telemetry.sink import MemoryTelemetrySink, utc_now

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")

_ALLOWED: dict[CallState, frozenset[CallState]] = {
    CallState.RECEIVED: frozenset({CallState.CONNECTED, CallState.FAILED}),
    CallState.CONNECTED: frozenset(
        {CallState.MEDIA_STARTED, CallState.FORWARDED, CallState.COMPLETED, CallState.FAILED}
    ),
    CallState.MEDIA_STARTED: frozenset({CallState.MEDIA_ENDED, CallState.FAILED}),
    CallState.MEDIA_ENDED: frozenset({CallState.COMPLETED, CallState.FORWARDED, CallState.FAILED}),
    CallState.FORWARDED: frozenset({CallState.COMPLETED, CallState.FAILED}),
    CallState.COMPLETED: frozenset(),
    CallState.FAILED: frozenset(),
}

_TERMINAL = frozenset({CallState.COMPLETED, CallState.FAILED})


class CallLifecycle:
    """Own state transitions and domain events for every provider."""

    def __init__(
        self,
        *,
        settings: Settings,
        store: InMemorySessionStore,
        bus: EventBus,
        telemetry: MemoryTelemetrySink,
        providers: dict[str, TelephonyProvider],
    ) -> None:
        self._settings = settings
        self._store = store
        self._bus = bus
        self._telemetry = telemetry
        self._providers = providers
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def handle_inbound(
        self,
        provider_name: str,
        body: bytes,
        content_type: str,
    ) -> tuple[CallSession, ProviderHttpResponse]:
        started = time.perf_counter()
        provider = self._provider(provider_name)
        inbound = await provider.receive_call(ProviderWebhookRequest(body=body, content_type=content_type))
        now = utc_now()
        session = CallSession(
            call_id=new_id("sb_"),
            provider=provider_name,
            provider_call_id=inbound.provider_call_id,
            from_number=inbound.from_number,
            to_number=inbound.to_number,
            direction=inbound.direction,
            state=CallState.RECEIVED,
            created_at=now,
            updated_at=now,
            provider_metadata=inbound.provider_metadata,
        )
        async with await self._lock_for(session.call_id):
            created = await self._store.add(session)
            if not created:
                raise InvalidRequest("duplicate provider call id")
            session = await self._attach_observation(
                session,
                source="webhook",
                raw=body,
                content_type=content_type,
                media=None,
            )
            await self._emit(
                session,
                "call.received",
                {
                    "provider_call_id": session.provider_call_id,
                    "from_number": session.from_number,
                    "to_number": session.to_number,
                    "direction": session.direction,
                },
            )
            session = await self._transition(
                session,
                CallState.CONNECTED,
                data={"provider_call_id": session.provider_call_id},
            )
            try:
                answer = provider.build_answer(session, self._settings.media_stream_url(provider_name))
            except ProviderConfigurationError:
                await self._fail(session.call_id, "media stream URL is not configured")
                raise
        self._timing("webhook.inbound", session, started)
        return session, answer

    async def handle_status(self, provider_name: str, body: bytes, content_type: str) -> CallSession:
        started = time.perf_counter()
        provider = self._provider(provider_name)
        update = await provider.parse_status_callback(ProviderWebhookRequest(body=body, content_type=content_type))
        existing = await self._store.get_by_provider_call(provider_name, update.provider_call_id)
        if existing is None:
            raise NotFoundError("unknown provider call")
        async with await self._lock_for(existing.call_id):
            session = await self._require(existing.call_id)
            session = await self._attach_observation(
                session,
                source="status",
                raw=body,
                content_type=content_type,
                media=None,
            )
            metadata = dict(session.provider_metadata)
            metadata["call_status"] = update.raw_status
            session = session.model_copy(update={"provider_metadata": metadata, "updated_at": utc_now()})
            await self._store.save(session)
            session = await self._apply_status(session.call_id, update.category, update.reason)
        self._timing("webhook.status", session, started)
        return session

    async def start_media(
        self,
        call_id: str,
        stream_id: str,
        *,
        encoding: str,
        sample_rate: int,
    ) -> CallSession:
        async with await self._lock_for(call_id):
            return await self._start_media(call_id, stream_id, encoding=encoding, sample_rate=sample_rate)

    async def observe_media(self, call_id: str, packet: InboundMediaPacket) -> CallSession:
        async with await self._lock_for(call_id):
            session = await self._require(call_id)
            if session.state is not CallState.MEDIA_STARTED:
                raise InvalidTransition("media packet received before the stream started")
            meta = MediaObservationMeta(
                sequence=packet.sequence,
                timestamp_ms=packet.timestamp_ms,
                encoding=packet.encoding,
                sample_rate=packet.sample_rate,
                track=packet.track,
            )
            session = await self._attach_observation(
                session,
                source="media",
                raw=packet.payload,
                content_type=packet.encoding,
                media=meta,
            )
            session = session.model_copy(
                update={"packets_observed": session.packets_observed + 1, "updated_at": utc_now()}
            )
            await self._store.save(session)
            self._telemetry.record(
                TelemetryRecord(
                    record_id=new_id("tm_"),
                    name="media.packet.observed",
                    recorded_at=utc_now(),
                    call_id=session.call_id,
                    provider=session.provider,
                    packets_in=session.packets_observed,
                    estimated_cost_usd=None,
                )
            )
            return session

    async def note_outbound(self, call_id: str) -> int:
        async with await self._lock_for(call_id):
            session = await self._require(call_id)
            session = session.model_copy(update={"packets_sent": session.packets_sent + 1, "updated_at": utc_now()})
            await self._store.save(session)
            self._telemetry.record(
                TelemetryRecord(
                    record_id=new_id("tm_"),
                    name="media.packet.sent",
                    recorded_at=utc_now(),
                    call_id=session.call_id,
                    provider=session.provider,
                    packets_out=session.packets_sent,
                    estimated_cost_usd=None,
                )
            )
            return session.packets_sent

    async def end_media(self, call_id: str) -> CallSession:
        async with await self._lock_for(call_id):
            return await self._end_media(call_id)

    async def hangup(self, call_id: str, reason: str) -> CallSession:
        async with await self._lock_for(call_id):
            return await self._hangup(call_id, reason)

    async def forward(self, call_id: str, destination: str) -> CallSession:
        if _E164.match(destination) is None:
            raise InvalidRequest("destination must be an E.164 number")
        async with await self._lock_for(call_id):
            return await self._forward(call_id, destination)

    async def get_session(self, call_id: str) -> CallSession:
        return await self._require(call_id)

    async def get_by_provider_call(self, provider: str, provider_call_id: str) -> CallSession | None:
        return await self._store.get_by_provider_call(provider, provider_call_id)

    async def get_status(self, call_id: str) -> ProviderCallStatus:
        session = await self._require(call_id)
        return await self._provider(session.provider).get_call_status(session)

    async def list_events(self, call_id: str) -> list[CallEvent]:
        await self._require(call_id)
        return await self._store.list_events(call_id)

    async def list_observations(self, call_id: str) -> list[RawObservation]:
        await self._require(call_id)
        return await self._store.list_observations(call_id)

    async def _apply_status(self, call_id: str, category: StatusCategory, reason: str) -> CallSession:
        match category:
            case StatusCategory.IGNORE:
                return await self._require(call_id)
            case StatusCategory.COMPLETED:
                return await self._hangup(call_id, reason)
            case StatusCategory.FAILED:
                return await self._fail(call_id, reason)
            case _:
                _never: Never = category
                raise RuntimeError(f"unhandled status category: {_never}")

    async def _start_media(
        self,
        call_id: str,
        stream_id: str,
        *,
        encoding: str,
        sample_rate: int,
    ) -> CallSession:
        session = await self._require(call_id)
        if session.state is CallState.MEDIA_STARTED and session.stream_id == stream_id:
            return session
        if session.state is not CallState.CONNECTED:
            raise InvalidTransition(f"cannot start media from {session.state.value}")
        provider = self._provider(session.provider)
        try:
            handle = await provider.open_media_stream(
                session,
                stream_id,
                encoding=encoding,
                sample_rate=sample_rate,
            )
        except ProviderError as exc:
            await self._fail(call_id, str(exc))
            raise ProviderSideEffectError(str(exc), call_id) from exc
        session = session.model_copy(
            update={
                "stream_id": handle.stream_id,
                "media_protocol": handle.protocol,
                "media_encoding": handle.encoding,
                "media_sample_rate": handle.sample_rate,
                "updated_at": utc_now(),
            }
        )
        await self._store.save(session)
        return await self._transition(
            session,
            CallState.MEDIA_STARTED,
            data={"stream_id": handle.stream_id, "protocol": handle.protocol},
        )

    async def _end_media(self, call_id: str) -> CallSession:
        session = await self._require(call_id)
        if session.state in {CallState.MEDIA_ENDED, CallState.COMPLETED, CallState.FAILED, CallState.FORWARDED}:
            return session
        if session.state is not CallState.MEDIA_STARTED:
            raise InvalidTransition(f"cannot end media from {session.state.value}")
        return await self._transition(
            session,
            CallState.MEDIA_ENDED,
            data={
                "stream_id": session.stream_id,
                "packets_observed": session.packets_observed,
                "packets_sent": session.packets_sent,
            },
        )

    async def _hangup(self, call_id: str, reason: str) -> CallSession:
        session = await self._require(call_id)
        if session.state in _TERMINAL:
            return session
        if session.state is CallState.MEDIA_STARTED:
            session = await self._end_media(call_id)
        provider = self._provider(session.provider)
        try:
            await provider.terminate_call(session, reason)
        except ProviderConfigurationError:
            raise
        except ProviderError as exc:
            await self._fail(call_id, str(exc))
            raise ProviderSideEffectError(str(exc), call_id) from exc
        session = await self._require(call_id)
        if session.state in _TERMINAL:
            return session
        return await self._transition(
            session,
            CallState.COMPLETED,
            data={"reason": reason},
            updates={"completion_reason": reason},
        )

    async def _forward(self, call_id: str, destination: str) -> CallSession:
        session = await self._require(call_id)
        if session.state is CallState.MEDIA_STARTED:
            session = await self._end_media(call_id)
        if session.state not in {CallState.CONNECTED, CallState.MEDIA_ENDED}:
            raise InvalidTransition(f"cannot forward from {session.state.value}")
        provider = self._provider(session.provider)
        try:
            await provider.forward_call(session, destination)
        except ProviderConfigurationError:
            raise
        except ProviderError as exc:
            await self._fail(call_id, str(exc))
            raise ProviderSideEffectError(str(exc), call_id) from exc
        session = await self._require(call_id)
        return await self._transition(
            session,
            CallState.FORWARDED,
            data={"destination": destination},
            updates={"forward_destination": destination},
        )

    async def _fail(self, call_id: str, reason: str) -> CallSession:
        session = await self._require(call_id)
        if session.state in _TERMINAL:
            return session
        if session.state is CallState.MEDIA_STARTED:
            session = await self._end_media(call_id)
        return await self._transition(
            session,
            CallState.FAILED,
            data={"reason": reason},
            updates={"failure_reason": reason},
        )

    async def _transition(
        self,
        session: CallSession,
        target: CallState,
        *,
        data: dict[str, Any],
        updates: dict[str, Any] | None = None,
    ) -> CallSession:
        if target not in _ALLOWED[session.state]:
            raise InvalidTransition(f"cannot move {session.state.value} to {target.value}")
        changed: dict[str, Any] = {"state": target, "updated_at": utc_now()}
        if updates:
            changed.update(updates)
        session = session.model_copy(update=changed)
        await self._store.save(session)
        await self._emit(session, _event_name(target), data)
        return session

    async def _emit(self, session: CallSession, name: EventName, data: dict[str, Any]) -> None:
        now = utc_now()
        elapsed_ms = max(int((now - session.created_at).total_seconds() * 1000), 0)
        event = CallEvent(
            event_id=new_id("ev_"),
            name=name,
            occurred_at=now,
            call_id=session.call_id,
            provider=session.provider,
            elapsed_ms=elapsed_ms,
            data=data,
        )
        await self._store.add_event(event)
        await self._bus.publish(event)

    async def _attach_observation(
        self,
        session: CallSession,
        *,
        source: Literal["webhook", "status", "media"],
        raw: bytes,
        content_type: str,
        media: MediaObservationMeta | None,
    ) -> CallSession:
        observation = RawObservation(
            observation_id=new_id("ob_"),
            call_id=session.call_id,
            provider=session.provider,
            observed_at=utc_now(),
            source=source,
            content_type=content_type,
            raw_b64=base64.b64encode(raw).decode("ascii"),
            byte_length=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            media=media,
        )
        await self._store.add_observation(observation)
        session = session.model_copy(
            update={
                "observation_ids": [*session.observation_ids, observation.observation_id],
                "updated_at": utc_now(),
            }
        )
        await self._store.save(session)
        return session

    async def _require(self, call_id: str) -> CallSession:
        session = await self._store.get(call_id)
        if session is None:
            raise NotFoundError("unknown call")
        return session

    def _provider(self, name: str) -> TelephonyProvider:
        provider = self._providers.get(name)
        if provider is None:
            raise NotFoundError(f"unknown telephony provider: {name}")
        return provider

    async def _lock_for(self, call_id: str) -> asyncio.Lock:
        async with self._guard:
            lock = self._locks.get(call_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[call_id] = lock
            return lock

    def _timing(self, name: str, session: CallSession, started: float) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._telemetry.record(
            TelemetryRecord(
                record_id=new_id("tm_"),
                name=name,
                recorded_at=utc_now(),
                call_id=session.call_id,
                provider=session.provider,
                duration_ms=duration_ms,
                elapsed_ms=duration_ms,
                estimated_cost_usd=None,
            )
        )


def _event_name(state: CallState) -> EventName:
    match state:
        case CallState.RECEIVED:
            return "call.received"
        case CallState.CONNECTED:
            return "call.connected"
        case CallState.MEDIA_STARTED:
            return "call.media.started"
        case CallState.MEDIA_ENDED:
            return "call.media.ended"
        case CallState.FORWARDED:
            return "call.forwarded"
        case CallState.COMPLETED:
            return "call.completed"
        case CallState.FAILED:
            return "call.failed"
        case _:
            _never: Never = state
            raise RuntimeError(f"unhandled call state: {_never}")
