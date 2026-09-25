"""Translate provider websocket frames into internal media commands."""

import base64
import binascii
import json
from abc import ABC, abstractmethod
from typing import Never

from switchboard.errors import FrameDecodeError
from switchboard.media.wire import parse_wire_format
from switchboard.models.media import (
    AudioCommand,
    AudioOutbound,
    CompletedOutbound,
    ErrorOutbound,
    HangupCommand,
    IgnoreCommand,
    MediaCommand,
    MediaEndedOutbound,
    OutboundMessage,
    ReadyOutbound,
    StartCommand,
    StopCommand,
    UnknownCommand,
)


class MediaFramer(ABC):
    protocol: str

    @abstractmethod
    def decode(self, text: str) -> MediaCommand:
        """Parse one websocket text frame."""

    @abstractmethod
    def encode(self, message: OutboundMessage) -> str | None:
        """Serialize an outbound message. None means the provider has no equivalent frame."""


class SwitchboardMediaFramer(MediaFramer):
    """JSON protocol used by the local simulator."""

    protocol = "switchboard.media.v1"

    def decode(self, text: str) -> MediaCommand:
        data = _object(text)
        kind = data.get("type")
        if kind == "start":
            encoding, sample_rate, channels = parse_wire_format(
                encoding=data.get("encoding"),
                sample_rate=data.get("sample_rate"),
                channels=data.get("channels"),
            )
            return StartCommand(
                call_id=_optional_str(data.get("call_id")),
                stream_id=_optional_str(data.get("stream_id")),
                encoding=encoding,
                sample_rate=sample_rate,
                channels=channels,
            )
        if kind == "media":
            encoding, sample_rate, channels = parse_wire_format(
                encoding=data.get("encoding"),
                sample_rate=data.get("sample_rate"),
                channels=data.get("channels"),
            )
            return AudioCommand(
                sequence=_as_int(data.get("sequence"), 0),
                timestamp_ms=_as_int(data.get("timestamp_ms"), 0),
                encoding=encoding,
                sample_rate=sample_rate,
                channels=channels,
                payload=_payload(data.get("payload_b64")),
                track=_str_or(data.get("track"), "inbound"),
            )
        if kind == "stop":
            return StopCommand()
        if kind == "hangup":
            return HangupCommand(
                reason=_str_or(data.get("reason"), "caller_hangup"),
                call_id=_optional_str(data.get("call_id")),
            )
        return UnknownCommand(detail=f"unsupported media frame type: {kind}")

    def encode(self, message: OutboundMessage) -> str | None:
        match message:
            case ReadyOutbound(call_id=call_id, stream_id=stream_id, protocol=protocol):
                return _dump({"type": "ready", "call_id": call_id, "stream_id": stream_id, "protocol": protocol})
            case AudioOutbound() as audio:
                return _dump(
                    {
                        "type": "media",
                        "call_id": audio.call_id,
                        "sequence": audio.sequence,
                        "encoding": audio.encoding,
                        "sample_rate": audio.sample_rate,
                        "channels": audio.channels,
                        "payload_b64": base64.b64encode(audio.payload).decode("ascii"),
                        "source": audio.source,
                    }
                )
            case MediaEndedOutbound(call_id=call_id):
                return _dump({"type": "media_ended", "call_id": call_id})
            case CompletedOutbound(call_id=call_id, reason=reason):
                return _dump({"type": "completed", "call_id": call_id, "reason": reason})
            case ErrorOutbound(detail=detail):
                return _dump({"type": "error", "detail": detail})
            case _:
                _never: Never = message
                raise RuntimeError(f"unhandled outbound message: {_never}")


class TwilioMediaFramer(MediaFramer):
    """Twilio Media Streams JSON (connected, start, media, stop, mark)."""

    protocol = "twilio.media.v1"

    def decode(self, text: str) -> MediaCommand:
        data = _object(text)
        event = data.get("event")
        if event in {"connected", "mark"}:
            return IgnoreCommand()
        if event == "start":
            return _twilio_start(data)
        if event == "media":
            return _twilio_media(data)
        if event == "stop":
            return StopCommand()
        return UnknownCommand(detail=f"unsupported twilio media event: {event}")

    def encode(self, message: OutboundMessage) -> str | None:
        match message:
            case AudioOutbound(stream_id=stream_id, payload=payload):
                body: dict[str, object] = {
                    "event": "media",
                    "media": {"payload": base64.b64encode(payload).decode("ascii")},
                }
                if stream_id:
                    body["streamSid"] = stream_id
                return _dump(body)
            case ReadyOutbound() | MediaEndedOutbound() | CompletedOutbound() | ErrorOutbound():
                return None
            case _:
                _never: Never = message
                raise RuntimeError(f"unhandled outbound message: {_never}")


def _twilio_start(data: dict[str, object]) -> StartCommand:
    start = data.get("start")
    start_map = start if isinstance(start, dict) else {}
    call_sid = start_map.get("callSid") or data.get("callSid")
    stream_sid = data.get("streamSid") or start_map.get("streamSid")
    media_format = start_map.get("mediaFormat")
    format_map = media_format if isinstance(media_format, dict) else {}
    if not isinstance(call_sid, str) or not call_sid:
        raise FrameDecodeError("twilio start is missing callSid")
    stream_id = stream_sid if isinstance(stream_sid, str) and stream_sid else None
    encoding, sample_rate, channels = parse_wire_format(
        encoding=format_map.get("encoding"),
        sample_rate=format_map.get("sampleRate"),
        channels=format_map.get("channels"),
    )
    return StartCommand(
        provider_call_id=call_sid,
        stream_id=stream_id,
        encoding=encoding,
        sample_rate=sample_rate,
        channels=channels,
    )


def _twilio_media(data: dict[str, object]) -> AudioCommand:
    media = data.get("media")
    if not isinstance(media, dict):
        raise FrameDecodeError("twilio media frame is missing media")
    sequence = media.get("chunk")
    if sequence is None:
        sequence = data.get("sequenceNumber")
    return AudioCommand(
        sequence=_as_int(sequence, 0),
        timestamp_ms=_as_int(media.get("timestamp"), 0),
        encoding="audio/x-mulaw",
        sample_rate=8000,
        channels=1,
        payload=_payload(media.get("payload")),
        track=_str_or(media.get("track"), "inbound"),
    )


def _object(text: str) -> dict[str, object]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FrameDecodeError("media frame is not JSON") from exc
    if not isinstance(data, dict):
        raise FrameDecodeError("media frame must be a JSON object")
    return data


def _dump(payload: dict[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def _payload(value: object) -> bytes:
    if not isinstance(value, str) or value == "":
        raise FrameDecodeError("audio payload is missing")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise FrameDecodeError("audio payload is not valid base64") from exc


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    raise FrameDecodeError("expected a string field")


def _str_or(value: object, default: str) -> str:
    if isinstance(value, str) and value:
        return value
    return default


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default
