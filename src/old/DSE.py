import heapq
import pandas as pd
from enum import Enum


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

class Block:
    def __init__(self, env: DSEEnvironment, name: str, ledger: Ledger):
        self.env = env
        self.name = name
        self.ledger = ledger
        self._us_rr_idx = 0
        self.downstream_blocks: list[Block] = []
        self.upstream_blocks: list[Block] = []

    def connect(self, downstream_block: Block):
        self.downstream_blocks.append(downstream_block)
        downstream_block.upstream_blocks.append(self)
        self._us_rr_idx = 0


    # here we apply logic to accept or reject entity
    # Reason to reject 
    # 1. No space to take on the entity
    # 2. Entity does not want to come here 
    def can_receive(self, entity: Entity = None):
        return True
    
    # upstream --> current
    # Assumes the can receive is true 
    # takes on entity and begins processing this must produce a future event or
    # or the entity will forever remain
    def receive(self, entity: Entity):
        self.ledger.log(self.env, entity, self, EventType.ENTITY_RECEIVED)
    

    ### 
    def try_receive_from_upstream(self):
        num_upstream = len(self.upstream_blocks)
        if num_upstream == 0:
            return
        for idx in range(num_upstream):
            target_idx = (idx + self._us_rr_idx) % num_upstream
            upstream_block = self.upstream_blocks[target_idx]
            upstream_block.handle_downstream_can_receive()
        self._us_rr_idx = (self._us_rr_idx + 1) % num_upstream
    
    # current --> downstream
    def send(self, entity: Entity) -> Entity:
        

        # when ever we send an entity we should try to receive a new one 
        # from upstream
        self.try_receive_from_upstream()


class Event():

    def __init__(self, time: float, typ: EventType, id: int, block_name: str):
        
        self.time = time
        self.typ = typ
        self.eid = id

    # Define the less than operator for the heap insertion, order by earliest time or event id as tiebreaker
    def __lt__(self, other: 'Event') -> bool:
        if self.time == other.time:
            return self.id < other.id
        return self.time < other.time

class DSEEnvironment: 
    def __init__(self, blocks: list[Block], block_connections: list[tuple[int, int]]):
        self.time = 0.0
        self.future_event_set: list[Event] = []
        self.eid = 0
        self.blocks = blocks

        # apply the block connections
        for origin, destination in block_connections:
            self.blocks[origin].connect(self.blocks[destination])

    def add_future_event(self, dt, callback, *args, **kwargs):
        event_time = self.time + dt
        e = Event(event_time, callback, args, kwargs, self.eid)
        heapq.heappush(self.future_event_set, e)
        self.eid += 1

    def run(self, end_time):
        while self.future_event_set and self.future_event_set[0].time < end_time:
            e: Event = heapq.heappop(self.future_event_set)
            self.time = e.time
            # e.callback(*e.args, **e.kwargs)

            


class Entity:
    __slots__ = ['id', 'creation_time', 'type']
    def __init__(self, id, creation_time, entity_type: EntityTypes):
        self.id = id
        self.creation_time = creation_time
        self.type = entity_type

class Ledger:
    def __init__(self):
        self.records = []

    def log(self, env: DSEEnvironment, entity: Entity, block: 'Block', event_type: EventType):
        self.records.append({
            'time': env.time, 
            'entity_id': entity.id,
            'entity_type': entity.type.name if hasattr(entity.type, 'name') else entity.type,
            'block': block.name, 
            'event': event_type.name
        })
    
    def to_dataframe(self):
        return pd.DataFrame(self.records)

class Block:
    def __init__(self, env: DSEEnvironment, name: str, ledger: Ledger):
        self.env = env
        self.name = name
        self.ledger = ledger
        self._us_rr_idx = 0
        self.downstream_blocks: list[Block] = []
        self.upstream_blocks: list[Block] = []

    def connect(self, downstream_block: Block):
        self.downstream_blocks.append(downstream_block)
        downstream_block.upstream_blocks.append(self)
        self._us_rr_idx = 0

    def can_receive(self, entity: Entity = None):
        return True
    
    def receive(self, entity: Entity):
        self.ledger.log(self.env, entity, self, EventType.ENTITY_RECEIVED)
    
    def notify_upstream_can_receive(self):
        num_upstream = len(self.upstream_blocks)
        if num_upstream == 0:
            return
        for idx in range(num_upstream):
            target_idx = (idx + self._us_rr_idx) % num_upstream
            upstream_block = self.upstream_blocks[target_idx]
            upstream_block.handle_downstream_can_receive()
        self._us_rr_idx = (self._us_rr_idx + 1) % num_upstream

    def handle_downstream_can_receive(self):
        pass