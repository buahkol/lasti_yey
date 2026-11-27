import re
from dataclasses import dataclass
from datetime import date, datetime

from ..models import Batch, BatchStatus, InspectionStatus, Product
from ..services import BatchService, ProductService
from .rules import inspection_status

_CODE = re.compile(r"^B-\d{4}-\d{2}$")
PAGE_SIZE = 7

# Tab filters on the Batch page: (label, filter key)
FILTERS = [("Semua", None), ("Berjalan", "running"), ("PASSED", "passed"), ("HOLD", "hold")]


@dataclass
class CreateResult:
    ok: bool
    error: str | None = None  # "format" or "duplicate"
    batch: Batch | None = None


class BatchController:
    """Batch list, create and close (FR-05, FR-06, FR-26, FR-27)."""

    def __init__(self, batches: BatchService, products: ProductService):
        self._batches = batches
        self._products = products

    # queries -------------------------------------------------------------
    def products(self) -> list[Product]:
        return self._products.list_products()

    @staticmethod
    def _matches(batch: Batch, key: str | None) -> bool:
        if key == "running":
            return batch.running
        if key == "passed":
            return not batch.running and batch.inspection == InspectionStatus.PASSED
        if key == "hold":
            return not batch.running and batch.inspection == InspectionStatus.HOLD
        return True

    def search(self, key: str | None = None, sku: str | None = None, query: str = "",
               start: date | None = None, end: date | None = None) -> list[Batch]:
        """Batches that match the tab filter, product, search text and date range."""
        q = query.strip().upper()
        result = []
        for b in self._batches.list_batches():
            if not self._matches(b, key):
                continue
            if sku and b.sku != sku:
                continue
            if q and q not in b.code:
                continue
            if start and b.started_at.date() < start:
                continue
            if end and b.started_at.date() > end:
                continue
            result.append(b)
        return result

    def tab_counts(self, **filters) -> list[int]:
        """Number of batches per tab, using the same product, search and date filters."""
        return [len(self.search(key, **filters)) for _, key in FILTERS]

    @staticmethod
    def page(rows: list, page: int) -> list:
        return rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    @staticmethod
    def page_count(rows: list) -> int:
        return max(1, -(-len(rows) // PAGE_SIZE))

    # commands ------------------------------------------------------------
    def create(self, code: str, product: Product) -> CreateResult:
        code = code.strip().upper()
        if not _CODE.match(code):
            return CreateResult(False, "format")
        if self._batches.find(code):
            return CreateResult(False, "duplicate")
        batch = Batch(code, product.sku, product.name, datetime.now(), "berjalan 0 menit", 0, 0.0,
                      BatchStatus.RUNNING, InspectionStatus.HOLD)
        return CreateResult(True, None, self._batches.add(batch))

    def close(self, code: str) -> Batch | None:
        """Close a running batch; its final status follows the NG tolerance (FR-26)."""
        batch = self._batches.find(code)
        if batch is None or not batch.running:
            return batch
        batch.status = BatchStatus.CLOSED
        batch.inspection = inspection_status(batch.ng_percent)
        return self._batches.save(batch)
