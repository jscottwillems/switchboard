"""Hot-path seam. The WebSocket calls this after `recognize_frame` (SB-008)."""

import time
from collections.abc import Sequence
from uuid import UUID

from switchboard_conversation import FixedResponseSelector, ResponseSelector
from switchboard_observability import log_info
from switchboard_schemas.hotpath import ResponseDecision, ResponseRequest

from switchboard_media.ports import MockStt, MockTts, SttEvent, SttPort, TtsPort

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
    recognized: Sequence[SttEvent] | None = None,
    decisions: list[ResponseDecision] | None = None,
) -> bytes:
    """Run STT, then LOKI's selector, then TTS. Return the synthesized bytes.

    Pass `recognized` when `recognize_frame` already called `push_audio` for
    this payload. STT is not called again. `stt_ms` is then 0.

    `MockStt` returns no text for any payload other than the fixture frame, so
    a default call with no `recognized` stops after STT and returns `b""`.
    Durations are emitted after the audio bytes exist. If that emit raises, the
    bytes are still returned. This function does not publish events.

    When the selector runs, the decision is appended to `decisions` so the
    socket can publish that same decision.
    """

    stt_port = _stt if stt is None else stt
    tts_port = _tts if tts is None else tts
    selector_port = _selector if selector is None else selector

    if recognized is None:
        started = time.perf_counter()
        events = stt_port.push_audio(payload)
        stt_ms = _elapsed_ms(started)
    else:
        events = list(recognized)
        stt_ms = 0
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
    if decisions is not None:
        decisions.append(decision)

    started = time.perf_counter()
    audio = tts_port.synthesize(decision.text)
    tts_ms = _elapsed_ms(started)
    _emit_timing(stt_ms=stt_ms, select_ms=select_ms, tts_ms=tts_ms)
    return audio
