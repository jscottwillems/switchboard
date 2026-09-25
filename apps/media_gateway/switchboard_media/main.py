"""WebSocket skeleton. Frames are accepted and discarded. STT is not invoked."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from switchboard_schemas.api import HealthResponse
from switchboard_schemas.common import CONTRACT_VERSION
from switchboard_schemas.media import StreamReady
from switchboard_observability import log_info

from switchboard_media.settings import get_settings

app = FastAPI(title="Switchboard Media Gateway", version=CONTRACT_VERSION)
log_info("media_gateway_starting", redis_configured=bool(get_settings().redis_url))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="media_gateway", status="ok", version=CONTRACT_VERSION)


@app.websocket("/v1/streams")
async def streams(websocket: WebSocket, token: str | None = None) -> None:
    if not token:
        log_info("media_socket_rejected", reason="missing_token")
        await websocket.close(code=1008)
        return
    await websocket.accept()
    await websocket.send_json(StreamReady().model_dump())
    log_info("media_socket_ready")
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        return
    log_info("media_socket_closed")
