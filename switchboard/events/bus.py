"""Publish lifecycle events to in-process subscribers."""

from typing import Protocol

from switchboard.models.events import CallEvent


class EventHandler(Protocol):
    async def handle(self, event: CallEvent) -> None:
        """Receive one domain event. Handlers must not raise for routine work."""


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def publish(self, event: CallEvent) -> None:
        for handler in self._handlers:
            await handler.handle(event)
