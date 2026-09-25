"""Drive one fake inbound call through webhook, media, and hangup."""

import base64
import json
from dataclasses import dataclass

import httpx
import websockets

from switchboard.media.audio import fixed_response_frame
from switchboard.security.signatures import sign_mock_body

EXPECTED_EVENTS = (
    "call.received",
    "call.connected",
    "call.media.started",
    "call.media.ended",
    "call.completed",
)


@dataclass(frozen=True)
class SimulationResult:
    call_id: str
    events: tuple[str, ...]
    audio_reply_b64: str
    audio_matched: bool
    observed_sha256: str | None
    final_state: str
    ok: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "events": list(self.events),
            "audio_reply_b64": self.audio_reply_b64,
            "audio_matched": self.audio_matched,
            "observed_sha256": self.observed_sha256,
            "final_state": self.final_state,
            "ok": self.ok,
        }


async def drive_call(
    *,
    base_url: str,
    secret: str,
    from_number: str = "+15551110000",
    to_number: str = "+15552220000",
    provider_call_id: str | None = None,
    audio_payload: bytes | None = None,
) -> SimulationResult:
    """Place a signed mock call, send one audio frame, then hang up."""

    payload: dict[str, str] = {"from": from_number, "to": to_number}
    if provider_call_id is not None:
        payload["provider_call_id"] = provider_call_id
    body = json.dumps(payload).encode("utf-8")
    signature = sign_mock_body(secret, body)
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        response = await client.post(
            "/webhooks/mock/voice",
            content=body,
            headers={
                "content-type": "application/json",
                "X-Switchboard-Signature": signature,
            },
        )
        response.raise_for_status()
        answered = response.json()
        call_id = answered["call_id"]
        media_url = answered["media_stream_url"]
        packet = audio_payload if audio_payload is not None else b"\x10\x20\x30\x40"
        reply_b64 = await _stream(media_url, call_id, packet)
        detail = await client.get(f"/calls/{call_id}")
        detail.raise_for_status()
        document = detail.json()
    events = tuple(event["name"] for event in document["events"])
    observed = _media_sha(document["observations"])
    expected_audio = base64.b64encode(fixed_response_frame()).decode("ascii")
    audio_matched = reply_b64 == expected_audio
    final_state = document["session"]["state"]
    ok = audio_matched and events == EXPECTED_EVENTS and final_state == "completed"
    return SimulationResult(
        call_id=call_id,
        events=events,
        audio_reply_b64=reply_b64,
        audio_matched=audio_matched,
        observed_sha256=observed,
        final_state=final_state,
        ok=ok,
    )


async def _stream(media_url: str, call_id: str, packet: bytes) -> str:
    async with websockets.connect(media_url) as socket:
        await socket.send(json.dumps({"type": "start", "call_id": call_id}))
        ready = json.loads(await socket.recv())
        if ready.get("type") != "ready":
            raise RuntimeError(f"media stream did not become ready: {ready}")
        await socket.send(
            json.dumps(
                {
                    "type": "media",
                    "sequence": 1,
                    "timestamp_ms": 0,
                    "encoding": "audio/x-mulaw",
                    "sample_rate": 8000,
                    "payload_b64": base64.b64encode(packet).decode("ascii"),
                }
            )
        )
        reply = json.loads(await socket.recv())
        if reply.get("type") != "media":
            raise RuntimeError(f"media stream did not return audio: {reply}")
        await socket.send(json.dumps({"type": "hangup", "reason": "caller_hangup"}))
        seen: list[str] = []
        while True:
            message = json.loads(await socket.recv())
            seen.append(message.get("type", ""))
            if message.get("type") == "completed":
                break
        if "media_ended" not in seen:
            raise RuntimeError(f"hangup did not end media: {seen}")
        return str(reply.get("payload_b64", ""))


def _media_sha(observations: list[dict[str, object]]) -> str | None:
    for observation in observations:
        if observation.get("source") == "media":
            sha = observation.get("sha256")
            if isinstance(sha, str):
                return sha
    return None
