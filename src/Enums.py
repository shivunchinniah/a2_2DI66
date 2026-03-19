from enum import Enum
from typing import NamedTuple, Callable, Any
import numpy as np

class CustomerState(Enum):
    WAITING: 0
    SERVICE: 1
   
class WasteType(Enum):
    TYPE_A = 0 # Tuinafval & grond
    TYPE_B = 1 # Includes all non-hazardous recyclable materials
    TYPE_DCDD = 2 # Clean and dirty rubble
    TYPE_REST = 3 # Others including hazardous materials

class VehicleSize(Enum):
    SMALL = 0
    BIG = 1

class EntityTypes(Enum):
    CUSTOMER = 0

# 
class EventType(Enum):
    ENTITY_RECEIVED = 0
    ENTITY_CREATED = 1
    ENTITY_DESTROYED = 2
    # CUSTOMER_LEAVES_QUEUE_BEGINS_SERVICE = 1
    # CUSTOMER_ENDS_SERVICE = 3

class Event(NamedTuple):
    time: float
    callback: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = {}
    eid: int

    def __lt__(self, other: 'Event') -> bool:
        if self.time == other.time:
            return self.eid < other.eid
        return self.time < other.time
