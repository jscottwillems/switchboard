from fastapi import APIRouter, Depends

from switchboard_schemas.api import (
    IssueStreamTokenRequest,
    IssueStreamTokenResponse,
    ValidateStreamTokenRequest,
    ValidateStreamTokenResponse,
)

from switchboard_api.auth import require_internal_token
from switchboard_api.memory_tokens import issue_token, validate_token

router = APIRouter(
    prefix="/v1/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_token)],
)


@router.post("/stream-tokens", response_model=IssueStreamTokenResponse)
def post_stream_token(body: IssueStreamTokenRequest) -> IssueStreamTokenResponse:
    return issue_token(body.call_session_id)


@router.post("/stream-tokens/validate", response_model=ValidateStreamTokenResponse)
def post_validate_token(body: ValidateStreamTokenRequest) -> ValidateStreamTokenResponse:
    return validate_token(body.token)
