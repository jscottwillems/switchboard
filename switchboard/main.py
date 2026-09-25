"""FastAPI application factory."""

from fastapi import APIRouter, FastAPI

from switchboard.api.calls import router as call_router
from switchboard.api.errors import register_exception_handlers
from switchboard.api.media import router as media_router
from switchboard.api.webhooks import router as webhook_router
from switchboard.config import Settings
from switchboard.container import build_container
from switchboard.logging_config import configure_logging
from switchboard.providers.twilio import TwilioTransport

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "switchboard", "slice": "bell-telephony"}


def create_app(
    settings: Settings | None = None,
    *,
    twilio_transport: TwilioTransport | None = None,
) -> FastAPI:
    resolved = settings if settings is not None else Settings()
    configure_logging(resolved)
    app = FastAPI(
        title="Switchboard",
        version="0.1.0",
        summary="BELL telephony slice: webhook, call session, media stream, hangup",
    )
    app.state.container = build_container(resolved, twilio_transport=twilio_transport)
    app.include_router(health_router)
    app.include_router(webhook_router)
    app.include_router(call_router)
    app.include_router(media_router)
    register_exception_handlers(app)
    return app


app = create_app()
