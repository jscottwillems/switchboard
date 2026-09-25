import pytest
from pydantic import ValidationError

from switchboard_api.routes.telephony import render_instruction
from switchboard_telephony import VoiceInstructionRenderer, append_stream_token

STREAM_URL = "ws://localhost:8001/v1/streams"
TOKEN = "a" * 16


def test_renderer_enforces_stream_field_rules() -> None:
    renderer = VoiceInstructionRenderer()
    with pytest.raises(ValidationError):
        renderer.render("connect_stream")
    with pytest.raises(ValidationError):
        renderer.render("connect_stream", stream_url=STREAM_URL)
    with pytest.raises(ValidationError):
        renderer.render("connect_stream", stream_token=TOKEN)
    with pytest.raises(ValidationError):
        renderer.render("hangup", stream_token=TOKEN)
    with pytest.raises(ValidationError):
        renderer.render("reject", stream_url=STREAM_URL)
    with pytest.raises(ValueError, match="embedded"):
        renderer.render(
            "connect_stream",
            stream_url=f"{STREAM_URL}?token={TOKEN}",
            stream_token=TOKEN,
        )

    hangup = renderer.render("hangup")
    reject = renderer.render("reject")
    connect = renderer.render("connect_stream", stream_url=STREAM_URL, stream_token=TOKEN)
    assert hangup.action == "hangup"
    assert hangup.stream_url is None
    assert hangup.stream_token is None
    assert reject.action == "reject"
    assert reject.stream_token is None
    assert connect.stream_url == STREAM_URL
    assert connect.stream_token == TOKEN
    assert "token=" not in connect.stream_url


def test_carrier_adapter_appends_token_outside_the_instruction() -> None:
    instruction = VoiceInstructionRenderer().render(
        "connect_stream",
        stream_url=STREAM_URL,
        stream_token=TOKEN,
    )
    assert append_stream_token(instruction) == f"{STREAM_URL}?token={TOKEN}"
    queried = VoiceInstructionRenderer().render(
        "connect_stream",
        stream_url=f"{STREAM_URL}?codec=pcmu",
        stream_token=TOKEN,
    )
    assert append_stream_token(queried) == f"{STREAM_URL}?codec=pcmu&token={TOKEN}"
    with pytest.raises(ValueError):
        append_stream_token(VoiceInstructionRenderer().render("hangup"))
    with pytest.raises(ValueError):
        append_stream_token(VoiceInstructionRenderer().render("reject"))


def test_api_calls_renderer_for_each_action(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    original = VoiceInstructionRenderer.render

    def record(
        self: VoiceInstructionRenderer,
        action: str,
        *,
        stream_url: str | None = None,
        stream_token: str | None = None,
    ):
        calls.append(action)
        return original(self, action, stream_url=stream_url, stream_token=stream_token)

    monkeypatch.setattr(VoiceInstructionRenderer, "render", record)
    assert render_instruction("hangup").action == "hangup"
    assert render_instruction("reject").action == "reject"
    connected = render_instruction("connect_stream", stream_url=STREAM_URL, stream_token=TOKEN)
    assert connected.stream_url == STREAM_URL
    assert calls == ["hangup", "reject", "connect_stream"]
