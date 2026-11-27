"""Controllers: business rules between the services (data) and the views (src/ui/pages)."""

import os
from dataclasses import dataclass

from .. import services as sample
from ..services import ApiClient
from ..services import api as remote
from .alert_controller import AlertController
from .auth_controller import AuthController
from .batch_controller import BatchController, CreateResult
from .dashboard_controller import DashboardController
from .history_controller import HistoryController, PhotoFolder
from .event_controller import EventController
from .product_controller import ProductController
from .report_controller import ReportController


@dataclass
class Controllers:
    auth: AuthController
    dashboard: DashboardController
    products: ProductController
    batches: BatchController
    alerts: AlertController
    history: HistoryController
    reports: ReportController
    events: EventController

    api: ApiClient | None = None

    @classmethod
    def create(cls, use_api: bool | None = None, api: ApiClient | None = None) -> "Controllers":
        """Wire every controller to one shared set of services.

        use_api: True = REST API, False = sample data. Default: the API, unless SIMONPRO_SAMPLE=1.
        """
        if use_api is None:
            use_api = os.environ.get("SIMONPRO_SAMPLE", "") not in ("1", "true", "yes")
        if use_api:
            api = api or ApiClient()
            auth, products, batches = remote.AuthService(api), remote.ProductService(api), remote.BatchService(api)
            inspections, reports, events = (remote.InspectionService(api), remote.ReportService(api),
                                            remote.EventService(api))
        else:
            api = None
            auth, products, batches = sample.AuthService(), sample.ProductService(), sample.BatchService()
            inspections, reports, events = sample.InspectionService(), sample.ReportService(), sample.EventService()
        return cls(
            auth=AuthController(auth),
            dashboard=DashboardController(reports, inspections, batches),
            products=ProductController(products),
            batches=BatchController(batches, products),
            alerts=AlertController(inspections),
            history=HistoryController(inspections, batches, products),
            reports=ReportController(reports, batches, products),
            events=EventController(events, batches),
            api=api,
        )


__all__ = [
    "Controllers", "AuthController", "DashboardController", "ProductController", "BatchController",
    "CreateResult", "AlertController", "HistoryController", "PhotoFolder", "ReportController", "EventController",
]
