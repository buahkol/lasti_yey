"""Data access for the desktop app.

Two interchangeable sets of services with the same methods:

* ``api.py``: the SiMonPro REST API (default). Server address: SIMONPRO_API_URL.
* the classes below: fixed sample data matching the Figma screens (SIMONPRO_SAMPLE=1, and the tests).
"""

from .auth_service import AuthService
from .batch_service import BatchService
from .event_service import EventService
from .inspection_service import InspectionService
from .product_service import ProductService
from .report_service import ReportService

from .api_client import ApiClient, ApiError, ServerUnavailable, SessionExpired

__all__ = ["ApiClient", "ApiError", "ServerUnavailable", "SessionExpired", "AuthService", "BatchService", "EventService", "InspectionService", "ProductService", "ReportService"]
