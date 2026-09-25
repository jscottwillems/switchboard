from fastapi import APIRouter

from switchboard_schemas.api import HealthResponse
from switchboard_schemas.common import CONTRACT_VERSION

from switchboard_api.errors import ApiError
from switchboard_api.health_probes import tcp_reachable
from switchboard_api.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    if settings.health_probes and not (
        tcp_reachable(settings.database_url) and tcp_reachable(settings.redis_url)
    ):
        raise ApiError(
            503,
            "dependencies_unavailable",
            "Postgres or Redis did not accept a connection.",
        )
    return HealthResponse(service="api", status="ok", version=CONTRACT_VERSION)
