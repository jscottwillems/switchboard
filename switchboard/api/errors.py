"""Map expected telephony errors onto HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from switchboard.errors import (
    InvalidRequest,
    InvalidTransition,
    NotFoundError,
    ProviderConfigurationError,
    ProviderPayloadError,
    ProviderSideEffectError,
    WebhookVerificationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WebhookVerificationError)
    async def unverified(request: Request, exc: WebhookVerificationError) -> JSONResponse:
        del request, exc
        return JSONResponse(status_code=401, content={"detail": "webhook signature verification failed"})

    @app.exception_handler(ProviderPayloadError)
    async def bad_payload(request: Request, exc: ProviderPayloadError) -> JSONResponse:
        del request
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidRequest)
    async def bad_request(request: Request, exc: InvalidRequest) -> JSONResponse:
        del request
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def missing(request: Request, exc: NotFoundError) -> JSONResponse:
        del request
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransition)
    async def conflict(request: Request, exc: InvalidTransition) -> JSONResponse:
        del request
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderConfigurationError)
    async def unconfigured(request: Request, exc: ProviderConfigurationError) -> JSONResponse:
        del request
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ProviderSideEffectError)
    async def side_effect(request: Request, exc: ProviderSideEffectError) -> JSONResponse:
        del request
        return JSONResponse(status_code=502, content={"detail": str(exc), "call_id": exc.call_id})
