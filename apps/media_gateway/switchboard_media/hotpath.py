"""Hot-path seam. The WebSocket handler does not call this yet (SB-008)."""

from uuid import UUID

from switchboard_conversation import FixedResponseSelector, ResponseSelector
from switchboard_schemas.hotpath import ResponseRequest

from switchboard_media.ports import MockStt, MockTts, SttPort, TtsPort

_stt: SttPort = MockStt()
_tts: TtsPort = MockTts()
_selector: ResponseSelector = FixedResponseSelector()


def respond_to_audio(call_session_id: UUID, turn_index: int, payload: bytes) -> bytes:
    """Run mock STT, then the response selector, then mock TTS.

    Mock STT returns no text, so the selector and TTS are not reached.
    """

    events = _stt.push_audio(payload)
    finals = [event for event in events if event.is_final and event.text]
    if not finals:
        return b""
    decision = _selector.select(
        ResponseRequest(
            call_session_id=call_session_id,
            turn_index=turn_index,
            latest_caller_text=finals[-1].text,
        )
    )
    return _tts.synthesize(decision.text)
