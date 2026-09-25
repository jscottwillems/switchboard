"""Media stream websocket. One provider framer per path."""

from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["media"])


@router.websocket("/media/stream/{provider}")
async def media_stream(websocket: WebSocket, provider: str) -> None:
    container = websocket.app.state.container
    if provider not in container.framers:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    await container.gateway.handle(websocket, provider)
