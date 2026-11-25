"""Data access for the desktop app.

The services read the sample data in sample_data.py for now. When the REST
API is ready, replace the body of each method with a call to the API client;
controllers and views do not need to change.
"""

from .auth_service import AuthService
from .batch_service import BatchService
from .inspection_service import InspectionService
from .product_service import ProductService
from .report_service import ReportService

__all__ = ["AuthService", "BatchService", "InspectionService", "ProductService", "ReportService"]
