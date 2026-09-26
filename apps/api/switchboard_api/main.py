import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from switchboard_observability import log_info

from switchboard_api.errors import register_error_handlers
from switchboard_api.projector import projector_worker_enabled, serve_projector
from switchboard_api.routes import calls, campaigns, health, internal, telephony
from switchboard_api.settings import get_settings


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    stop = threading.Event()
    thread: threading.Thread | None = None
    if projector_worker_enabled():
        thread = threading.Thread(
            target=serve_projector,
            args=(stop,),
            name="api.projector",
            daemon=True,
        )
        thread.start()
    try:
        yield
    finally:
        stop.set()
        if thread is not None:
            thread.join(timeout=2.0)


settings = get_settings()
log_info(
    "api_starting",
    env=settings.env,
    database_configured=bool(settings.database_url),
    redis_configured=bool(settings.redis_url),
)

app = FastAPI(title="Switchboard API", version=settings.contract_version, lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Switchboard-Internal-Token",
        "X-Switchboard-Mock-Signature",
    ],
)
register_error_handlers(app)
app.include_router(health.router)
app.include_router(telephony.router)
app.include_router(calls.router)
app.include_router(campaigns.router)
app.include_router(internal.router)
