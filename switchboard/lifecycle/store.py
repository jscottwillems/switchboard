"""Process-local session store.

ADR-001 records why Redis and Postgres are not on the hot path yet. The
store returns copies so callers can edit a snapshot and save it back.
"""

import asyncio

from switchboard.models.events import CallEvent
from switchboard.models.media import RawObservation
from switchboard.models.session import CallSession


class InMemorySessionStore:
    """Async-safe in-memory sessions, observations, and domain events."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, CallSession] = {}
        self._by_provider_call: dict[tuple[str, str], str] = {}
        self._observations: dict[str, list[RawObservation]] = {}
        self._events: dict[str, list[CallEvent]] = {}

    async def add(self, session: CallSession) -> bool:
        """Insert a session. Return False when the provider call id is already stored."""

        async with self._lock:
            key = (session.provider, session.provider_call_id)
            if key in self._by_provider_call:
                return False
            self._sessions[session.call_id] = session
            self._by_provider_call[key] = session.call_id
            self._observations.setdefault(session.call_id, [])
            self._events.setdefault(session.call_id, [])
            return True

    async def save(self, session: CallSession) -> None:
        async with self._lock:
            self._sessions[session.call_id] = session
            self._by_provider_call[(session.provider, session.provider_call_id)] = session.call_id

    async def get(self, call_id: str) -> CallSession | None:
        async with self._lock:
            session = self._sessions.get(call_id)
            if session is None:
                return None
            return session.model_copy(deep=True)

    async def get_by_provider_call(self, provider: str, provider_call_id: str) -> CallSession | None:
        async with self._lock:
            call_id = self._by_provider_call.get((provider, provider_call_id))
            if call_id is None:
                return None
            session = self._sessions.get(call_id)
            if session is None:
                return None
            return session.model_copy(deep=True)

    async def add_observation(self, observation: RawObservation) -> None:
        async with self._lock:
            self._observations.setdefault(observation.call_id, []).append(observation)

    async def list_observations(self, call_id: str) -> list[RawObservation]:
        async with self._lock:
            return [item.model_copy(deep=True) for item in self._observations.get(call_id, [])]

    async def add_event(self, event: CallEvent) -> None:
        async with self._lock:
            self._events.setdefault(event.call_id, []).append(event)

    async def list_events(self, call_id: str) -> list[CallEvent]:
        async with self._lock:
            return [item.model_copy(deep=True) for item in self._events.get(call_id, [])]
