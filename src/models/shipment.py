from dataclasses import dataclass
from datetime import datetime


@dataclass
class Shipment:
    shipment_id: int
    order_id: str
    batch_codes: list[str]
    quantity: int
    created_at: datetime
