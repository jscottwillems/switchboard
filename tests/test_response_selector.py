"""SB-007: empty caller text is less certain than a real utterance."""

import ast
import socket
from pathlib import Path
from uuid import uuid4

import pytest
from switchboard_conversation import (
    EMPTY_CALLER_TEXT_CONFIDENCE,
    FIXED_REPLY,
    FIXED_STRATEGY_ID,
    FixedResponseSelector,
)
from switchboard_schemas.events import ConversationResponseSelected
from switchboard_schemas.hotpath import ResponseRequest

_CONVERSATION_ROOT = Path(__file__).resolve().parents[1] / "packages" / "conversation"
_MAX_SPOKEN_WORDS = 12


def _request(text: str) -> ResponseRequest:
    return ResponseRequest(call_session_id=uuid4(), turn_index=0, latest_caller_text=text)


def _word_count(text: str) -> int:
    return len(text.split())


def test_empty_caller_text_confidence_is_below_one() -> None:
    decision = FixedResponseSelector().select(_request(""))
    assert decision.confidence < 1
    assert decision.confidence == EMPTY_CALLER_TEXT_CONFIDENCE
    assert decision.text == FIXED_REPLY
    assert decision.strategy_id == FIXED_STRATEGY_ID
    assert decision.text.strip()
    assert "\n" not in decision.text
    assert _word_count(decision.text) <= _MAX_SPOKEN_WORDS


@pytest.mark.parametrize("text", ["", " ", "\n", "\t", " \n\t "])
def test_blank_caller_text_is_empty(text: str) -> None:
    decision = FixedResponseSelector().select(_request(text))
    assert decision.confidence < 1
    assert decision.text == FIXED_REPLY


def test_non_empty_caller_text_keeps_the_fixed_reply() -> None:
    decision = FixedResponseSelector().select(_request("hello"))
    assert decision.text == FIXED_REPLY
    assert decision.strategy_id == FIXED_STRATEGY_ID
    assert decision.confidence == 1.0
    assert _word_count(decision.text) <= _MAX_SPOKEN_WORDS


def test_surrounding_whitespace_still_counts_as_caller_text() -> None:
    decision = FixedResponseSelector().select(_request("  hello  "))
    assert decision.confidence == 1.0
    assert decision.text == FIXED_REPLY


def test_decision_fills_conversation_response_selected() -> None:
    """Hot-path output uses the 0.1.0 turn-decision fields, nothing else."""

    decision = FixedResponseSelector().select(_request(""))
    payload = ConversationResponseSelected(
        turn_id=uuid4(),
        strategy_id=decision.strategy_id,
        text=decision.text,
        confidence=decision.confidence,
    )
    assert payload.confidence < 1
    assert payload.confidence == decision.confidence
    assert payload.text == decision.text
    assert payload.strategy_id == decision.strategy_id


def test_selector_source_does_not_import_network_clients() -> None:
    banned = {"socket", "http", "urllib", "httpx", "requests", "aiohttp", "websocket"}
    for path in _CONVERSATION_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = {module.split(".", 1)[0]} if module else set()
            else:
                continue
            assert names.isdisjoint(banned), f"{path} imports {names & banned}"


def test_select_does_not_open_a_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("FixedResponseSelector attempted a network call")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)

    selector = FixedResponseSelector()
    empty = selector.select(_request(""))
    spoken = selector.select(_request("I need you to verify a payment"))
    assert empty.confidence < 1
    assert spoken.text == FIXED_REPLY
    assert spoken.confidence == 1.0
