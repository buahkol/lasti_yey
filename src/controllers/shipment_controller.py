from dataclasses import dataclass, field

from ..models import Batch, InspectionStatus, Shipment
from ..services import BatchService, ShipmentService

ORDER_LIMIT = 50


@dataclass
class SubmitResult:
    shipment: Shipment | None = None
    errors: dict = field(default_factory=dict)
    hold_batches: list = field(default_factory=list)


class ShipmentController:
    def __init__(self, shipments: ShipmentService, batches: BatchService):
        self._shipments = shipments
        self._batches = batches

    def shipments(self) -> list[Shipment]:
        return self._shipments.list_shipments()

    def passed_batches(self) -> list[Batch]:
        return [b for b in self._batches.list_batches() if self._is_passed(b)]

    @staticmethod
    def _is_passed(batch: Batch) -> bool:
        return not batch.running and batch.inspection == InspectionStatus.PASSED

    @staticmethod
    def parse_quantity(value: str) -> int | None:
        digits = value.strip().replace(".", "")
        return int(digits) if digits.isdigit() else None

    def submit(self, order_id: str, batch_codes: list[str], quantity: str) -> SubmitResult:
        errors = {}
        order_id = order_id.strip().upper()
        if not order_id:
            errors["order"] = "Isi nomor pesanan."
        elif len(order_id) > ORDER_LIMIT:
            errors["order"] = f"Nomor pesanan paling banyak {ORDER_LIMIT} karakter."
        batches = [self._batches.find(c) for c in batch_codes]
        unknown = [c for c, b in zip(batch_codes, batches) if b is None]
        if not batch_codes:
            errors["batches"] = "Pilih minimal satu batch."
        elif unknown:
            errors["batches"] = f"Batch {', '.join(unknown)} tidak terdaftar."
        qty = self.parse_quantity(quantity)
        if not qty:
            errors["quantity"] = "Isi jumlah kaleng dengan angka lebih dari 0."
        if errors:
            return SubmitResult(errors=errors)
        hold = [b.code for b in batches if not self._is_passed(b)]
        if hold:
            return SubmitResult(hold_batches=hold)
        return SubmitResult(self._shipments.create(order_id, batch_codes, qty))
