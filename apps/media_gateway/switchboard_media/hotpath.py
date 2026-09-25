"""Hot-path seam. The WebSocket handler does not call this yet (SB-008)."""

import time
from uuid import UUID

from switchboard_conversation import FixedResponseSelector, ResponseSelector
from switchboard_observability import log_info
from switchboard_schemas.hotpath import ResponseRequest

from switchboard_media.ports import MockStt, MockTts, SttPort, TtsPort

_stt: SttPort = MockStt()
_tts: TtsPort = MockTts()
_selector: ResponseSelector = FixedResponseSelector()


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def emit_hotpath_timing(
    *,
    stt_ms: int,
    select_ms: int | None = None,
    tts_ms: int | None = None,
) -> None:
    """Emit stage durations through the observability helper. No text and no audio."""

    fields: dict[str, object] = {"stt_ms": stt_ms}
    if select_ms is not None:
        fields["select_ms"] = select_ms
    if tts_ms is not None:
        fields["tts_ms"] = tts_ms
    log_info("hotpath_timing", **fields)


def _emit_timing(
    *,
    stt_ms: int,
    select_ms: int | None = None,
    tts_ms: int | None = None,
) -> None:
    """A metrics failure must not discard audio already produced."""

    try:
        emit_hotpath_timing(stt_ms=stt_ms, select_ms=select_ms, tts_ms=tts_ms)
    except Exception:
        try:
            log_info("hotpath_timing_failed")
        except Exception:
            return


def respond_to_audio(
    call_session_id: UUID,
    turn_index: int,
    payload: bytes,
    *,
    stt: SttPort | None = None,
    tts: TtsPort | None = None,
    selector: ResponseSelector | None = None,
) -> bytes:
    """Run STT, then LOKI's selector, then TTS. Return the synthesized bytes.

    Mock STT returns no text, so the default call stops after STT and returns `b""`.
    Durations are emitted after the audio bytes exist. If that emit raises, the
    bytes are still returned.
    """

    stt_port = _stt if stt is None else stt
    tts_port = _tts if tts is None else tts
    selector_port = _selector if selector is None else selector

    started = time.perf_counter()
    events = stt_port.push_audio(payload)
    stt_ms = _elapsed_ms(started)
    finals = [event for event in events if event.is_final and event.text]
    if not finals:
        _emit_timing(stt_ms=stt_ms)
        return b""

    started = time.perf_counter()
    decision = selector_port.select(
        ResponseRequest(
            call_session_id=call_session_id,
            turn_index=turn_index,
            latest_caller_text=finals[-1].text,
        )
    )
    select_ms = _elapsed_ms(started)

    started = time.perf_counter()
    audio = tts_port.synthesize(decision.text)
    tts_ms = _elapsed_ms(started)
    _emit_timing(stt_ms=stt_ms, select_ms=select_ms, tts_ms=tts_ms)
    return audio
