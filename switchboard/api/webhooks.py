"""Inbound carrier webhooks. Signature checks happen before session creation."""

from fastapi import APIRouter, Depends, Request, Response

from switchboard.api.deps import get_container
from switchboard.container import Container
from switchboard.errors import NotFoundError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{provider}/voice")
async def inbound_voice(
    provider: str,
    request: Request,
    container: Container = Depends(get_container),
) -> Response:
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    _verify(container, provider, body, request, f"/webhooks/{provider}/voice")
    session, answer = await container.lifecycle.handle_inbound(provider, body, content_type)
    del session
    return Response(content=answer.body, media_type=answer.media_type, status_code=answer.status_code)


@router.post("/{provider}/status")
async def status_callback(
    provider: str,
    request: Request,
    container: Container = Depends(get_container),
) -> Response:
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    _verify(container, provider, body, request, f"/webhooks/{provider}/status")
    session = await container.lifecycle.handle_status(provider, body, content_type)
    return Response(
        content=session.model_dump_json(),
        media_type="application/json",
        status_code=200,
    )


def _verify(container: Container, provider: str, body: bytes, request: Request, path: str) -> None:
    verifier = container.verifiers.get(provider)
    if verifier is None or provider not in container.providers:
        raise NotFoundError(f"unknown telephony provider: {provider}")
    url = container.settings.public_url(path)
    headers = {key: value for key, value in request.headers.items()}
    verifier.verify(body=body, headers=headers, url=url)
