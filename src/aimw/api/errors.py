"""Centralised API exceptions + handlers (uniform ErrorResponse contract)."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..domain.schemas import ErrorResponse
from ..logging_config import get_logger

log = get_logger(__name__)


class APIError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found", detail: str | None = None) -> None:
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(request: Request, exc: APIError) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=exc.message, detail=exc.detail, request_id=rid).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="validation_error", detail=str(exc.errors()), request_id=rid
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        log.error("api.unhandled", error=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="internal_error", detail="An unexpected error occurred", request_id=rid
            ).model_dump(),
        )
