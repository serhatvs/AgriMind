"""Exports for ingestion client abstractions and built-in clients."""

from app.ingestion.clients.base import IngestionClient
from app.ingestion.clients.faostat import FAOSTATAPIClient, FAOSTATBulkDownloadClient, FAOSTATIngestionClient
from app.ingestion.clients.http_json import HTTPJSONClient
from app.ingestion.clients.nasa_power import NASAPowerAPIClient, NASAPowerFetchResult, NASAPowerIngestionClient

__all__ = [
    "FAOSTATAPIClient",
    "FAOSTATBulkDownloadClient",
    "FAOSTATIngestionClient",
    "HTTPJSONClient",
    "IngestionClient",
    "NASAPowerAPIClient",
    "NASAPowerFetchResult",
    "NASAPowerIngestionClient",
]
