"""Exports for ingestion client abstractions and built-in clients."""

from app.ingestion.clients.base import IngestionClient
from app.ingestion.clients.faostat import FAOSTATBulkDownloadClient, FAOSTATIngestionClient
from app.ingestion.clients.http_json import HTTPJSONClient
from app.ingestion.clients.nasa_power import NASAPowerAPIClient, NASAPowerIngestionClient

__all__ = [
    "FAOSTATBulkDownloadClient",
    "FAOSTATIngestionClient",
    "HTTPJSONClient",
    "IngestionClient",
    "NASAPowerAPIClient",
    "NASAPowerIngestionClient",
]
