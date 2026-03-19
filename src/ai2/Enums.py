from enum import Enum
from typing import NamedTuple, Callable, Any

class EventType(Enum):
    ENTITY_RECEIVED = 0
    ENTITY_CREATED = 1
    ENTITY_DESTROYED = 2
    ENTITY_ROUTED = 3
    SERVICE_STARTED = 4
    SERVICE_COMPLETED = 5

class WasteType(Enum):
    TYPE_A = 0
    TYPE_B = 1
    TYPE_DCDD = 2
    TYPE_REST = 3

class VehicleSize(Enum):
    SMALL = 0
    BIG = 1

class EntityTypes(Enum):
    CUSTOMER = 0

class Event(NamedTuple):
    time: float
    callback: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = {}
    eid: int = 0

    def __lt__(self, other: 'Event') -> bool:
        if self.time == other.time:
            return self.eid < other.eid
        return self.time < other.time