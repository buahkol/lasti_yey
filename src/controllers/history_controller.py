from dataclasses import dataclass

from ..models import Alert, Batch, Inspection
from ..services import BatchService, InspectionService, ProductService

PAGE_SIZE = 20
FILTERS = [("Semua", None), ("OK", "OK"), ("NG", "NG")]


@dataclass
class PhotoFolder:
    """All saved photos (OK and NG) of one batch, shown as a folder on the Riwayat page."""

    batch: Batch
    preview: list[Alert]  # the latest photos, for the folder thumbnail

    @property
    def count(self) -> int:
        return self.batch.output

    @property
    def ok(self) -> int:
        return self.batch.ok_count

    @property
    def ng(self) -> int:
        return self.batch.ng_count


class HistoryController:
    """Riwayat: a photo folder per batch with every inspected can, OK and NG (FR-30, FR-31).

    Photos are kept without a time limit so a batch can be traced when a complaint comes in.
    """

    def __init__(self, inspections: InspectionService, batches: BatchService, products: ProductService):
        self._inspections = inspections
        self._batches = batches
        self._products = products

    def _threshold(self, batch: Batch) -> float:
        product = self._products.find(batch.sku)
        return product.threshold if product else 0.6

    def as_photo(self, batch: Batch, row: Inspection) -> Alert:
        """The photo viewer and cards read Alert objects; this adds threshold, product and result."""
        return Alert(row.batch, f"{row.timestamp:%H.%M.%S}", row.score, self._threshold(batch),
                     row.defect if row.is_ng else "none", batch.product, row.timestamp, row.result, row.inspection_id)

    def folders(self, query: str = "") -> list[PhotoFolder]:
        """Folders newest first. query matches the batch code, SKU or product name."""
        q = query.strip().upper()
        result = []
        for b in sorted(self._batches.list_batches(), key=lambda x: x.started_at, reverse=True):
            if q and q not in b.code.upper() and q not in b.sku.upper() and q not in b.product.upper():
                continue
            rows = self._inspections.history(b.code)[:3]
            result.append(PhotoFolder(b, [self.as_photo(b, r) for r in rows]))
        return result

    def folder(self, code: str) -> PhotoFolder | None:
        code = code.strip().upper()
        b = self._batches.find(code)
        if b is None:
            return None
        return PhotoFolder(b, [self.as_photo(b, r) for r in self._inspections.history(code)[:3]])

    def counts(self, code: str) -> list[int]:
        rows = self._inspections.history(code)
        return [len(rows), sum(1 for r in rows if not r.is_ng), sum(1 for r in rows if r.is_ng)]

    def photos(self, code: str, result: str | None = None, page: int = 0) -> tuple[list[Alert], int, int]:
        """One page of photos. Returns (photos, page count, matching total)."""
        b = self._batches.find(code)
        if b is None:
            return [], 1, 0
        rows = [r for r in self._inspections.history(code) if result is None or r.result == result]
        pages = max(1, -(-len(rows) // PAGE_SIZE))
        page = max(0, min(page, pages - 1))
        chunk = rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        return [self.as_photo(b, r) for r in chunk], pages, len(rows)
