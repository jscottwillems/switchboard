from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from switchboard_schemas.api import ErrorBody


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, message: str) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        body = ErrorBody(error=exc.error, message=exc.message)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    def handle_validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        body = ErrorBody(error="invalid_request", message="Request failed validation.")
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(HTTPException)
    def handle_http(_request: Request, exc: HTTPException) -> JSONResponse:
        codes = {401: "unauthorized", 403: "forbidden", 404: "not_found"}
        error = codes.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else error
        body = ErrorBody(error=error, message=message)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())
