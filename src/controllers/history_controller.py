from dataclasses import dataclass

from ..models import Batch, Inspection
from ..services import BatchService, InspectionService

PAGE_SIZE = 10
RESULT_FILTERS = [("Semua", None), ("OK", "OK"), ("NG", "NG")]


@dataclass
class History:
    code: str
    batch: Batch | None
    rows: list[Inspection]
    total: int
    ng: int

    @property
    def ok(self) -> int:
        return self.total - self.ng


class HistoryController:
    def __init__(self, inspections: InspectionService, batches: BatchService):
        self._inspections = inspections
        self._batches = batches

    @staticmethod
    def normalize(code: str) -> str:
        return code.strip().upper()

    def find(self, code: str) -> History | None:
        code = self.normalize(code)
        rows = self._inspections.history(code)
        if not rows:
            return None
        return History(code, self._batches.find(code), rows, len(rows), sum(r.is_ng for r in rows))

    @staticmethod
    def filtered(history: History, result: str | None) -> list[Inspection]:
        return [r for r in history.rows if result in (None, r.result)]

    @staticmethod
    def page(rows: list, page: int) -> list:
        return rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    @staticmethod
    def page_count(rows: list) -> int:
        return max(1, -(-len(rows) // PAGE_SIZE))
