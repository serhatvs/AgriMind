"""Ingestion-specific exception types."""


class IngestionError(Exception):
    """Base exception for ingestion pipeline failures."""


class IngestionConfigurationError(IngestionError):
    """Raised when an ingestion pipeline is configured incorrectly."""


class UnsupportedDataSourceTypeError(IngestionError):
    """Raised when no pipeline is registered for a source type."""
