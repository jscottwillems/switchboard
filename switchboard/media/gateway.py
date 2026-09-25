"""Websocket gateway. Vendor frames stay inside the framer."""

import anyio
from starlette.websockets import WebSocket, WebSocketDisconnect

from switchboard.errors import FrameDecodeError, InvalidTransition, NotFoundError
from switchboard.ids import new_id
from switchboard.lifecycle.service import CallLifecycle
from switchboard.media.framing import MediaFramer
from switchboard.media.pipeline import MediaPipeline
from switchboard.models.media import (
    AudioCommand,
    AudioOutbound,
    CompletedOutbound,
    ErrorOutbound,
    HangupCommand,
    IgnoreCommand,
    InboundMediaPacket,
    MediaEndedOutbound,
    OutboundMessage,
    ReadyOutbound,
    StartCommand,
    StopCommand,
    UnknownCommand,
)
from switchboard.models.session import CallSession, CallState

_MAX_PAYLOAD_BYTES = 65535


class MediaGateway:
    def __init__(
        self,
        *,
        lifecycle: CallLifecycle,
        framers: dict[str, MediaFramer],
        pipeline: MediaPipeline,
    ) -> None:
        self._lifecycle = lifecycle
        self._framers = framers
        self._pipeline = pipeline

    async def handle(self, websocket: WebSocket, provider_name: str) -> None:
        await websocket.accept()
        framer = self._framers[provider_name]
        bound: str | None = None
        close_reason = "websocket_disconnect"
        try:
            while True:
                incoming = await websocket.receive()
                if incoming["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(incoming.get("code", 1000))
                raw = incoming.get("text")
                if not isinstance(raw, str):
                    await self._send(websocket, framer, ErrorOutbound(detail="media frames must be JSON text"))
                    continue
                try:
                    command = framer.decode(raw)
                except FrameDecodeError as exc:
                    await self._send(websocket, framer, ErrorOutbound(detail=str(exc)))
                    continue
                match command:
                    case IgnoreCommand():
                        continue
                    case UnknownCommand(detail=detail):
                        await self._send(websocket, framer, ErrorOutbound(detail=detail))
                    case StartCommand() as start:
                        started = await self._on_start(websocket, framer, provider_name, start)
                        if started is not None:
                            bound = started
                    case AudioCommand() as audio:
                        if bound is None:
                            await self._send(websocket, framer, ErrorOutbound(detail="media arrived before start"))
                            continue
                        await self._on_audio(websocket, framer, bound, audio)
                    case StopCommand():
                        if bound is None:
                            await self._send(websocket, framer, ErrorOutbound(detail="stop arrived before start"))
                            continue
                        await self._lifecycle.end_media(bound)
                        await self._send(websocket, framer, MediaEndedOutbound(call_id=bound))
                    case HangupCommand(reason=reason, call_id=call_id):
                        if bound is None:
                            bound = call_id
                        if bound is None:
                            await self._send(websocket, framer, ErrorOutbound(detail="hangup requires an active call"))
                            continue
                        close_reason = reason
                        await self._finish(websocket, framer, bound, reason)
                        return
                    case _ as unmatched:
                        raise RuntimeError(f"unhandled media command: {unmatched!r}")
        except WebSocketDisconnect:
            pass
        finally:
            # The ASGI server may cancel this task as the socket closes. A shielded
            # scope lets hangup finish so the session does not stay in media_ended.
            if bound is not None:
                with anyio.CancelScope(shield=True):
                    await self._lifecycle.hangup(bound, close_reason)

    async def _on_start(
        self,
        websocket: WebSocket,
        framer: MediaFramer,
        provider_name: str,
        start: StartCommand,
    ) -> str | None:
        try:
            session = await self._resolve(provider_name, start)
        except (NotFoundError, FrameDecodeError) as exc:
            await self._send(websocket, framer, ErrorOutbound(detail=str(exc)))
            return None
        if session.provider != provider_name:
            await self._send(websocket, framer, ErrorOutbound(detail="call belongs to a different provider"))
            return None
        stream_id = start.stream_id or new_id("ms_")
        try:
            started = await self._lifecycle.start_media(
                session.call_id,
                stream_id,
                encoding=start.encoding,
                sample_rate=start.sample_rate,
            )
        except InvalidTransition as exc:
            await self._send(websocket, framer, ErrorOutbound(detail=str(exc)))
            return None
        if started.state is CallState.FAILED:
            await self._send(websocket, framer, ErrorOutbound(detail=started.failure_reason or "media start failed"))
            return None
        await self._send(
            websocket,
            framer,
            ReadyOutbound(
                call_id=started.call_id,
                stream_id=started.stream_id or stream_id,
                protocol=started.media_protocol or framer.protocol,
            ),
        )
        return started.call_id

    async def _on_audio(self, websocket: WebSocket, framer: MediaFramer, call_id: str, audio: AudioCommand) -> None:
        if len(audio.payload) == 0 or len(audio.payload) > _MAX_PAYLOAD_BYTES:
            await self._send(websocket, framer, ErrorOutbound(detail="audio payload must be 1 to 65535 bytes"))
            return
        packet = audio_to_packet(audio)
        try:
            await self._lifecycle.observe_media(call_id, packet)
            frame = await self._pipeline.handle_inbound(call_id, packet)
        except InvalidTransition as exc:
            await self._send(websocket, framer, ErrorOutbound(detail=str(exc)))
            return
        if frame is None:
            return
        sequence = await self._lifecycle.note_outbound(call_id)
        session = await self._lifecycle.get_session(call_id)
        await self._send(
            websocket,
            framer,
            AudioOutbound(
                call_id=call_id,
                stream_id=session.stream_id,
                sequence=sequence,
                encoding=frame.encoding,
                sample_rate=frame.sample_rate,
                payload=frame.payload,
                source=frame.source,
            ),
        )

    async def _finish(self, websocket: WebSocket, framer: MediaFramer, call_id: str, reason: str) -> None:
        current = await self._lifecycle.get_session(call_id)
        was_media = current.state is CallState.MEDIA_STARTED
        finished = await self._lifecycle.hangup(call_id, reason)
        if was_media:
            await self._send(websocket, framer, MediaEndedOutbound(call_id=call_id))
        if finished.state is CallState.COMPLETED:
            await self._send(
                websocket,
                framer,
                CompletedOutbound(call_id=call_id, reason=finished.completion_reason or reason),
            )
            return
        if finished.state is CallState.FAILED:
            await self._send(websocket, framer, ErrorOutbound(detail=finished.failure_reason or "call failed"))

    async def _resolve(self, provider_name: str, start: StartCommand) -> CallSession:
        if start.call_id:
            return await self._lifecycle.get_session(start.call_id)
        if start.provider_call_id:
            session = await self._lifecycle.get_by_provider_call(provider_name, start.provider_call_id)
            if session is None:
                raise NotFoundError("unknown provider call")
            return session
        raise FrameDecodeError("start requires call_id or provider call id")

    async def _send(self, websocket: WebSocket, framer: MediaFramer, message: OutboundMessage) -> None:
        encoded = framer.encode(message)
        if encoded is None:
            return
        await websocket.send_text(encoded)


def audio_to_packet(audio: AudioCommand) -> InboundMediaPacket:
    return InboundMediaPacket(
        sequence=audio.sequence,
        timestamp_ms=audio.timestamp_ms,
        encoding=audio.encoding,
        sample_rate=audio.sample_rate,
        payload=audio.payload,
        track=audio.track,
    )
