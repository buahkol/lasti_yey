from dataclasses import dataclass, field
from datetime import datetime

from ..models import Batch, ProductionEvent
from ..services import BatchService, EventService

PAGE_SIZE = 10
NOTE_LIMIT = 500
MANUAL_KINDS = [("BAHAN_BAKU_HABIS", "Bahan baku habis", "Kaleng, label, atau bahan isi habis"),
                ("ALAT_BERHENTI", "Alat berhenti", "Mesin atau konveyor berhenti bekerja")]


@dataclass
class RecordResult:
    event: ProductionEvent | None = None
    errors: dict = field(default_factory=dict)


class EventController:
    def __init__(self, events: EventService, batches: BatchService):
        self._events = events
        self._batches = batches

    def batches(self) -> list[Batch]:
        return self._batches.list_batches()

    def running_batches(self) -> list[Batch]:
        return [b for b in self._batches.list_batches() if b.running]

    def find_batch(self, code: str) -> Batch | None:
        return self._batches.find(code)

    def events(self, batch_code: str) -> list[ProductionEvent]:
        return self._events.list_events(batch_code)

    @staticmethod
    def page(rows: list, page: int) -> list:
        return rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    @staticmethod
    def page_count(rows: list) -> int:
        return max(1, -(-len(rows) // PAGE_SIZE))

    def record(self, batch_code: str, kind: str, note: str, when: datetime | None = None) -> RecordResult:
        errors = {}
        batch = self._batches.find(batch_code)
        if batch is None or not batch.running:
            errors["batch"] = "Pilih batch yang sedang berjalan."
        if kind not in [k for k, _, _ in MANUAL_KINDS]:
            errors["kind"] = "Pilih jenis kejadian."
        note = note.strip()
        if len(note) > NOTE_LIMIT:
            errors["note"] = f"Keterangan paling banyak {NOTE_LIMIT} karakter."
        if errors:
            return RecordResult(errors=errors)
        when = when or datetime.now()
        return RecordResult(self._events.record(batch_code, ProductionEvent(f"{when:%H.%M}", kind, "Operator", note)))
