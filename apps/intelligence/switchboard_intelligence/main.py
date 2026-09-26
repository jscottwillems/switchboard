import hmac
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from switchboard_classification import E164FindingExtractor
from switchboard_observability import log_info
from switchboard_schemas.api import ErrorBody, ExtractRequest, ExtractResponse, HealthResponse
from switchboard_schemas.common import CONTRACT_VERSION

from switchboard_intelligence.correlator_worker import correlator_worker_enabled, serve_correlator
from switchboard_intelligence.extractor_worker import extractor_worker_enabled, serve_extractor
from switchboard_intelligence.settings import get_settings


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    stop = threading.Event()
    threads: list[threading.Thread] = []
    if extractor_worker_enabled():
        threads.append(
            threading.Thread(
                target=serve_extractor,
                args=(stop,),
                name="intelligence.extractor",
                daemon=True,
            )
        )
    if correlator_worker_enabled():
        threads.append(
            threading.Thread(
                target=serve_correlator,
                args=(stop,),
                name="intelligence.correlator",
                daemon=True,
            )
        )
    for thread in threads:
        thread.start()
    try:
        yield
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=2.0)


app = FastAPI(title="Switchboard Intelligence", version=CONTRACT_VERSION, lifespan=_lifespan)
_extractor = E164FindingExtractor()
_settings = get_settings()
log_info(
    "intelligence_starting",
    database_configured=bool(_settings.database_url),
    redis_configured=bool(_settings.redis_url),
)


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, message: str) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message


@app.exception_handler(ApiError)
def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
    body = ErrorBody(error=exc.error, message=exc.message)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


def require_internal_token(
    x_switchboard_internal_token: str | None = Header(default=None),
) -> None:
    expected = get_settings().internal_token
    presented = x_switchboard_internal_token or ""
    if not expected or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise ApiError(401, "unauthorized", "Internal token was rejected.")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="intelligence", status="ok", version=CONTRACT_VERSION)


@app.post(
    "/v1/internal/extract",
    response_model=ExtractResponse,
    dependencies=[Depends(require_internal_token)],
)
def extract(body: ExtractRequest) -> ExtractResponse:
    return ExtractResponse(findings=_extractor.extract(body.segments))
