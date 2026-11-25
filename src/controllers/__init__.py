"""Controllers: business rules between the services (data) and the views (src/ui/pages)."""

from dataclasses import dataclass

from ..services import AuthService, BatchService, InspectionService, ProductService, ReportService
from .alert_controller import AlertController
from .auth_controller import AuthController
from .batch_controller import BatchController, CreateResult
from .dashboard_controller import DashboardController
from .product_controller import ProductController
from .report_controller import ReportController


@dataclass
class Controllers:
    auth: AuthController
    dashboard: DashboardController
    products: ProductController
    batches: BatchController
    alerts: AlertController
    reports: ReportController

    @classmethod
    def create(cls) -> "Controllers":
        """Wire every controller to one shared set of services."""
        auth, products, batches = AuthService(), ProductService(), BatchService()
        inspections, reports = InspectionService(), ReportService()
        return cls(
            auth=AuthController(auth),
            dashboard=DashboardController(reports, inspections, batches),
            products=ProductController(products),
            batches=BatchController(batches, products),
            alerts=AlertController(inspections),
            reports=ReportController(reports, batches, products),
        )


__all__ = [
    "Controllers", "AuthController", "DashboardController", "ProductController", "BatchController",
    "CreateResult", "AlertController", "ReportController",
]
