"""Media WebSocket. Parses switchboard.media.v1 and checks stream tokens.

Inbound audio is counted against the call budget and passed to mock STT.
A non-empty final is published as speech.segment.final, then the socket calls
respond_to_audio and publishes the conversation events (SB-008).
"""

import base64
import time
from collections.abc import Sequence

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect

from switchboard_observability import log_info
from switchboard_schemas.api import HealthResponse
from switchboard_schemas.common import CONTRACT_VERSION
from switchboard_schemas.hotpath import ResponseDecision
from switchboard_schemas.media import MEDIA_PROTOCOL, StreamMedia, StreamReady

from switchboard_media.budgets import admit_frame, new_budget
from switchboard_media.hotpath import respond_to_audio
from switchboard_media.ports import MOCK_TTS_FRAME_BYTES, MOCK_TTS_FRAME_MS
from switchboard_media.protocol import (
    CLOSE_NORMAL,
    CLOSE_POLICY_VIOLATION,
    MediaSession,
    frame_from_websocket_message,
    outbound_chunks,
)
from switchboard_media.recognition import RecognizedFinal, recognize_frame
from switchboard_media.reply import record_exchange
from switchboard_media.settings import get_settings
from switchboard_media.tokens import ApiStreamTokenValidator, StreamTokenValidator

app = FastAPI(title="Switchboard Media Gateway", version=CONTRACT_VERSION)
log_info("media_gateway_starting", redis_configured=bool(get_settings().redis_url))


def get_stream_token_validator() -> StreamTokenValidator:
    settings = get_settings()
    return ApiStreamTokenValidator(
        api_base_url=settings.api_base_url,
        internal_token=settings.internal_token,
        timeout_s=settings.stream_token_timeout_s,
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="media_gateway", status="ok", version=CONTRACT_VERSION)


async def _reject(websocket: WebSocket, reason: str, code: int = CLOSE_POLICY_VIOLATION) -> None:
    log_info("media_socket_rejected", reason=reason)
    await websocket.close(code=code)


async def _flush_outbound(websocket: WebSocket, session: MediaSession, sequence: int) -> int:
    while True:
        chunk = session.pop_outbound()
        if chunk is None:
            return sequence
        message = StreamMedia(
            sequence=sequence,
            timestamp_ms=sequence * MOCK_TTS_FRAME_MS,
            payload_b64=base64.b64encode(chunk).decode("ascii"),
        )
        await websocket.send_json(message.model_dump())
        session.mark_outbound_playing()
        sequence += 1


async def _speak_back(
    websocket: WebSocket,
    session: MediaSession,
    *,
    payload: bytes,
    finals: Sequence[RecognizedFinal],
    turn_index: int,
    outbound_sequence: int,
) -> tuple[int, int]:
    """Select, synthesize, publish, and write audio. Redis failures stay here."""

    if session.outbound_in_progress():
        await websocket.send_json(session.clear_outbound().model_dump())
    decisions: list[ResponseDecision] = []
    try:
        audio = respond_to_audio(
            session.call_session_id,
            turn_index + 1,
            payload,
            recognized=[final.event for final in finals],
            decisions=decisions,
        )
    except Exception:
        log_info(
            "hotpath_reply_failed",
            call_session_id=str(session.call_session_id),
            reason="reply_failed",
        )
        return turn_index, outbound_sequence
    if not decisions:
        return turn_index, outbound_sequence
    next_turn = record_exchange(
        session.call_session_id,
        turn_index,
        finals,
        decisions[0],
    )
    for chunk in outbound_chunks(audio, MOCK_TTS_FRAME_BYTES):
        session.enqueue_outbound(chunk)
    outbound_sequence = await _flush_outbound(websocket, session, outbound_sequence)
    return next_turn, outbound_sequence


@app.websocket("/v1/streams")
async def streams(
    websocket: WebSocket,
    validator: StreamTokenValidator = Depends(get_stream_token_validator),
    token: str | None = None,
) -> None:
    if not token:
        await _reject(websocket, "missing_token")
        return
    try:
        # Once per socket. Bounded by STREAM_TOKEN_VALIDATE_TIMEOUT_S.
        result = validator.validate(token)
    except Exception:
        await _reject(websocket, "validate_unavailable")
        return
    if not result.valid or result.call_session_id is None:
        await _reject(websocket, "invalid_token")
        return

    offered = websocket.scope.get("subprotocols") or []
    subprotocol = MEDIA_PROTOCOL if MEDIA_PROTOCOL in offered else None
    await websocket.accept(subprotocol=subprotocol)
    await websocket.send_json(StreamReady().model_dump())
    log_info("media_socket_ready", call_session_id=str(result.call_session_id))
    session = MediaSession(result.call_session_id)
    budget = new_budget()
    transcript_sequence = 0
    turn_index = 0
    outbound_sequence = 0
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message["type"] != "websocket.receive":
                continue
            payload = message.get("bytes") or b""
            text = message.get("text") or ""
            nbytes = len(payload) if payload else len(text.encode("utf-8"))
            decision = admit_frame(budget, nbytes, at=time.monotonic())
            if not decision.allowed:
                log_info("media_budget_denied", reason=decision.reason.value)
                await websocket.close(code=CLOSE_POLICY_VIOLATION)
                return
            outcome = frame_from_websocket_message(session, message)
            if outcome.audio is not None:
                # Audio bytes are not stored. A final is published; the samples are not.
                recognized = recognize_frame(
                    session.call_session_id,
                    outcome.audio.payload,
                    sequence=transcript_sequence,
                )
                transcript_sequence = recognized.next_sequence
                if recognized.finals:
                    turn_index, outbound_sequence = await _speak_back(
                        websocket,
                        session,
                        payload=outcome.audio.payload,
                        finals=recognized.finals,
                        turn_index=turn_index,
                        outbound_sequence=outbound_sequence,
                    )
            if outcome.close_code is not None:
                await _reject(
                    websocket,
                    outcome.reason or "invalid_message",
                    outcome.close_code,
                )
                return
            if outcome.stopped:
                log_info(
                    "media_socket_stopped",
                    audio_frames=session.audio_frames,
                    stream_id=session.stream_id,
                )
                await websocket.close(code=CLOSE_NORMAL)
                return
    except WebSocketDisconnect:
        return
    log_info("media_socket_closed")
