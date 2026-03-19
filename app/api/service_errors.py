"""Translate service-layer exceptions into HTTP responses."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException

from app.services.errors import ConflictError, NotFoundError, ServiceValidationError


def raise_http_exception_for_service_error(exc: Exception) -> NoReturn:
    """Raise an HTTPException with the correct status for a service-layer error."""

    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ServiceValidationError):
        raise HTTPException(status_code=400, detail=str(exc))
    raise exc
