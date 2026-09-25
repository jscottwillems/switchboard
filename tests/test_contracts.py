"""Draft event fixtures and the lifecycle boundary."""

import asyncio
import json
from pathlib import Path

import pytest

from switchboard.config import Settings
from switchboard.errors import InvalidTransition
from switchboard.main import create_app
from switchboard.models.events import EVENT_NAMES, CallEvent
from switchboard.models.telemetry import TelemetryRecord

FIXTURES = Path("docs/fixtures/events")
REQUIRED = {
    "call.received",
    "call.connected",
    "call.media.started",
    "call.media.ended",
    "call.forwarded",
    "call.completed",
    "call.failed",
}


def test_event_names_are_the_contract() -> None:
    assert set(EVENT_NAMES) == REQUIRED


def test_event_fixtures_match_the_schema() -> None:
    paths = sorted(FIXTURES.glob("*.json"))
    assert {path.stem for path in paths} == REQUIRED
    for path in paths:
        event = CallEvent.model_validate_json(path.read_text())
        assert event.name == path.stem
        assert event.record_type == "interpretation"


def test_telemetry_fixture() -> None:
    record = TelemetryRecord.model_validate_json(Path("docs/fixtures/telemetry/call.completed.json").read_text())
    assert record.record_type == "telemetry"
    assert record.estimated_cost_usd is None


def test_lifecycle_does_not_name_a_vendor() -> None:
    source = Path("switchboard/lifecycle/service.py").read_text().lower()
    assert "twilio" not in source
    assert "fastapi" not in source


def test_concurrent_inbound_sessions_stay_distinct() -> None:
    app = create_app(
        Settings(
            public_base_url="http://test",
            media_ws_base_url="ws://test",
            mock_webhook_secret="test-secret",
            log_level="WARNING",
        )
    )

    async def place(index: int):
        body = json.dumps(
            {"from": f"+1555000{index:04d}", "to": "+15552220000", "provider_call_id": f"concurrent-{index}"}
        ).encode()
        session, _answer = await app.state.container.lifecycle.handle_inbound("mock", body, "application/json")
        return session

    async def scenario():
        return await asyncio.gather(*(place(index) for index in range(8)))

    sessions = asyncio.run(scenario())
    assert len({session.call_id for session in sessions}) == 8
    assert {session.state.value for session in sessions} == {"connected"}


def test_second_media_stream_is_rejected() -> None:
    app = create_app(
        Settings(
            public_base_url="http://test",
            media_ws_base_url="ws://test",
            mock_webhook_secret="test-secret",
            log_level="WARNING",
        )
    )

    async def scenario() -> None:
        body = b'{"from":"+15551119","to":"+15552220000","provider_call_id":"one-stream"}'
        session, _answer = await app.state.container.lifecycle.handle_inbound("mock", body, "application/json")
        lifecycle = app.state.container.lifecycle
        await lifecycle.start_media(session.call_id, "ms_one", encoding="audio/x-mulaw", sample_rate=8000)
        with pytest.raises(InvalidTransition):
            await lifecycle.start_media(session.call_id, "ms_two", encoding="audio/x-mulaw", sample_rate=8000)

    asyncio.run(scenario())
