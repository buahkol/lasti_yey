import copy

from ..models import ProductionEvent
from . import sample_data


class EventService:
    def __init__(self):
        self._events = copy.deepcopy(sample_data.EVENTS)

    def list_events(self, batch_code: str) -> list[ProductionEvent]:
        return list(self._events.get(batch_code, []))

    def record(self, batch_code: str, event: ProductionEvent) -> ProductionEvent:
        self._events.setdefault(batch_code, []).insert(0, event)
        return event
