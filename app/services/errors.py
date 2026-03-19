"""Shared service-layer exceptions."""


class ServiceError(Exception):
    """Base exception type for service-layer failures."""


class NotFoundError(ServiceError):
    """Raised when a referenced resource does not exist."""


class ConflictError(ServiceError):
    """Raised when a write would violate a business-level uniqueness rule."""


class ServiceValidationError(ServiceError):
    """Raised when a request is structurally valid but violates service rules."""
