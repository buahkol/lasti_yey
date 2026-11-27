import copy

from ..models import Batch
from . import sample_data


class BatchService:
    """GET/POST /batches and POST /batches/{code}/close (FR-05, FR-06, FR-27)."""

    def __init__(self):
        self._batches = copy.deepcopy(sample_data.BATCHES)

    def list_batches(self) -> list[Batch]:
        return list(self._batches)

    def find(self, code: str) -> Batch | None:
        return next((b for b in self._batches if b.code == code), None)

    def add(self, batch: Batch) -> Batch:
        self._batches.insert(0, batch)
        return batch

    def close(self, batch: Batch, inspection: str) -> Batch:
        """Close a running batch with the inspection status decided by the controller (FR-26)."""
        batch.status = "DITUTUP"
        batch.inspection = inspection
        return batch

    def save(self, batch: Batch) -> Batch:
        """Persist status changes. In-memory objects are already updated."""
        return batch
