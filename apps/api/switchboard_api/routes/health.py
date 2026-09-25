from fastapi import APIRouter

from switchboard_schemas.api import HealthResponse
from switchboard_schemas.common import CONTRACT_VERSION

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="api", status="ok", version=CONTRACT_VERSION)
