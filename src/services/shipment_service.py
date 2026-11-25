import copy
from datetime import datetime

from ..models import Shipment
from . import sample_data


class ShipmentService:
    def __init__(self):
        self._shipments = copy.deepcopy(sample_data.SHIPMENTS)

    def list_shipments(self) -> list[Shipment]:
        return list(self._shipments)

    def create(self, order_id: str, batch_codes: list[str], quantity: int) -> Shipment:
        next_id = max((s.shipment_id for s in self._shipments), default=0) + 1
        shipment = Shipment(next_id, order_id, list(batch_codes), quantity, datetime.now())
        self._shipments.insert(0, shipment)
        return shipment
