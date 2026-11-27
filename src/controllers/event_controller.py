import re
from dataclasses import dataclass, field
from datetime import datetime

from ..models import Batch, ProductionEvent
from ..services import BatchService, EventService

PAGE_SIZE = 10
NOTE_LIMIT = 500
KIND_LIMIT = 40
# Suggestions in the Jenis kejadian field. The operator may also type a new type.
MANUAL_KINDS = [("BAHAN_BAKU_HABIS", "Bahan baku habis", "Kaleng, label, atau bahan isi habis"),
                ("ALAT_BERHENTI", "Alat berhenti", "Mesin atau konveyor berhenti bekerja")]
# Recorded by the system only, never by the operator.
SYSTEM_KINDS = {"REJECT", "RATE_DROP"}


def kind_label(code: str) -> str:
    """BAHAN_BAKU_HABIS -> 'Bahan baku habis'."""
    known = {k: label for k, label, _ in MANUAL_KINDS}
    return known.get(code, code.replace("_", " ").capitalize())


def resolve_kind(value: str) -> tuple[str | None, str | None]:
    """Turn the typed or picked event type into a code such as ALAT_BERHENTI. Returns (code, error)."""
    value = " ".join(value.split())
    if not value:
        return None, "Isi atau pilih jenis kejadian."
    for code, label, _ in MANUAL_KINDS:
        if value.lower() in (code.lower(), label.lower(), code.replace("_", " ").lower()):
            return code, None
    if len(value) > KIND_LIMIT:
        return None, f"Jenis kejadian paling banyak {KIND_LIMIT} karakter."
    code = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    if not code:
        return None, "Jenis kejadian harus berisi huruf atau angka."
    if code in SYSTEM_KINDS:
        return None, "REJECT dan RATE_DROP dicatat otomatis oleh sistem."
    return code, None


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

    def kind_suggestions(self) -> list[tuple[str, str, str]]:
        """Preset types plus types typed earlier, so they can be picked again."""
        known = {k for k, _, _ in MANUAL_KINDS} | SYSTEM_KINDS
        typed = []
        for b in self._batches.list_batches():
            for e in self._events.list_events(b.code):
                if e.kind not in known and e.kind not in typed:
                    typed.append(e.kind)
        return list(MANUAL_KINDS) + [(k, kind_label(k), "Diketik sebelumnya") for k in typed]

    def record(self, batch_code: str, kind: str, note: str, when: datetime | None = None) -> RecordResult:
        """kind may be a code (ALAT_BERHENTI), a label (Alat berhenti) or a new type typed by the operator."""
        errors = {}
        batch = self._batches.find(batch_code)
        if batch is None or not batch.running:
            errors["batch"] = "Pilih batch yang sedang berjalan."
        kind, kind_error = resolve_kind(kind)
        if kind_error:
            errors["kind"] = kind_error
        note = note.strip()
        if len(note) > NOTE_LIMIT:
            errors["note"] = f"Keterangan paling banyak {NOTE_LIMIT} karakter."
        if errors:
            return RecordResult(errors=errors)
        when = when or datetime.now()
        return RecordResult(self._events.record(batch_code, ProductionEvent(f"{when:%H.%M}", kind, "Operator", note)))
