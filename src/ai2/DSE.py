import heapq
import pandas as pd
from Enums import Event, EventType, EntityTypes

class DSEEnvironment: 
    def __init__(self):
        self.time = 0.0
        self.future_event_set: list[Event] = []
        self.eid = 0

    def add_future_event(self, dt, callback, *args, **kwargs):
        event_time = self.time + dt
        e = Event(event_time, callback, args, kwargs, self.eid)
        heapq.heappush(self.future_event_set, e)
        self.eid += 1

    def run(self, end_time):
        while self.future_event_set and self.future_event_set[0].time < end_time:
            e = heapq.heappop(self.future_event_set)
            self.time = e.time
            e.callback(*e.args, **e.kwargs)

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
        self.next_blocks: list['Block'] = []
        self.upstream_blocks: list['Block'] = []

    def connect(self, next_block: 'Block'):
        self.next_blocks.append(next_block)
        next_block.upstream_blocks.append(self)
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