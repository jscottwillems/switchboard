from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from switchboard_observability import log_info

from switchboard_api.errors import register_error_handlers
from switchboard_api.routes import calls, campaigns, health, internal, telephony
from switchboard_api.settings import get_settings

settings = get_settings()
log_info(
    "api_starting",
    env=settings.env,
    database_configured=bool(settings.database_url),
    redis_configured=bool(settings.redis_url),
)

app = FastAPI(title="Switchboard API", version=settings.contract_version)
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
