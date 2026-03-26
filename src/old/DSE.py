import numpy as np
import heapq
from collections import deque
import itertools
from Enums import Event, EventType, EntityType
import pandas as pd
from Sampler import Sampler


class DSEEnvironment: 
    def __init__(self):
        self.time = 0.0
        self.future_event_set: list[Event] = []
        self.eid = 0

    def add_future_event(self, dt, callback, *args, **kwargs):
        event_time = self.time + dt
        e = Event(event_time, callback, args, kwargs, self.eid)
        heapq.heappush(self.future_event_set, e)

        # increment event id
        self.eid += 1

    def run(self, end_time):
        # Run while there are events and  the next event is before the end time
        while self.future_event_set and self.future_event_set[0].time < end_time:
            e = heapq.heappop(self.future_event_set)
            self.time = e.time
            e.callback(*e.args, **e.kwargs)


class Entity:

    __slots__ = ['id', 'creation_time']

    def __init__(self, id, creation_time, entity_type: EntityType):
        self.id = id
        self.creation_time = creation_time
        self.type = entity_type

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
        # The exception has been removed. This now safely acts as a logging 
        # interceptor for all subclass receive methods.
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


class QueueBlock(Block):
    def __init__(self, env, name, ledger, capacity):
        super().__init__(env, name, ledger)
        self.capacity = capacity
        self.fifo = deque()
        self._ds_rr_idx  = 0

    def connect(self, next_block):
        self._ds_rr_idx = 0
        return super().connect(next_block)

    def can_receive(self, entity):
        return len(self.fifo) < self.capacity
    
    def receive(self, entity):
        # Call base class to log ENTITY_RECEIVED
        super().receive(entity)
        self.fifo.append(entity)
        self._try_push()

    def _try_push(self):
        while self.fifo and self.next_blocks:
            entity_pushed = False
            num_downstream = len(self.next_blocks)
            
            for idx in range(num_downstream):
                target_idx = (idx + self._ds_rr_idx) % num_downstream
                target_server = self.next_blocks[target_idx]
                
                if target_server.can_receive(self.fifo[0]):
                    # Corrected to popleft() to maintain FIFO order
                    entity = self.fifo.popleft() 
                    
                    if len(self.fifo) == self.capacity - 1:
                        self.notify_upstream_can_receive()
                        
                    target_server.receive(entity)
                    self._ds_rr_idx = (target_idx + 1) % num_downstream
                    entity_pushed = True
                    break 
            
            if not entity_pushed:
                break

    def handle_downstream_can_receive(self):
        self._try_push()


class JunctionBlock(Block):
    def __init__(self, env, name, ledger, routing_func):
        super().__init__(env, name, ledger)
        self.routing_func = routing_func

    def can_receive(self, entity = None):
        next_block = self.routing_func(entity, self.next_blocks)
        return next_block.can_receive(entity)
    
    def receive(self, entity):
        # Call base class to log ENTITY_RECEIVED
        super().receive(entity)
        
        # Corrected signature: passing 'self' instead of 'self.name'
        # Note: Ensure EventType.ENTITY_ROUTED exists in your Enums
        self.ledger.log(self.env, entity, self, EventType.ENTITY_ROUTED)
        
        target = self.routing_func(entity, self.next_blocks)
        target.receive(entity)

    def handle_downstream_can_receive(self):
        self.notify_upstream_can_receive()


class ServiceBlock(Block):
    def __init__(self, env, name, ledger, service_time_dist: Sampler):
        super().__init__(env, name, ledger)
        self.service_time_dist = service_time_dist
        self.is_busy = False
        self.blocked_entity: Entity = None

    def can_receive(self, entity = None):
        return not self.is_busy and self.blocked_entity is None
    
    def receive(self, entity):
        # Call base class to log ENTITY_RECEIVED
        super().receive(entity)
        
        self.is_busy = True
        self.env.add_future_event(
            dt = self.service_time_dist.sample(),
            callback=self._finish,
            entity=entity
        )
    
    def _finish(self, entity: Entity):
        if not self.next_blocks:
            self.is_busy = False
            self.notify_upstream_can_receive()
            return

        next_block = self.next_blocks[0]

        if next_block.can_receive(entity = entity):
            next_block.receive(entity = entity)
            self.is_busy = False
            self.notify_upstream_can_receive()
        else:
            self.blocked_entity = entity

    def handle_downstream_can_receive(self):
        if self.blocked_entity:
            next_block = self.next_blocks[0]

            if next_block.can_receive(entity = self.blocked_entity):
                entity_to_send = self.blocked_entity 
                self.is_busy = False
                self.blocked_entity = None

                next_block.receive(entity = entity_to_send)
                self.notify_upstream_can_receive()


class DestroyerBlock(Block):
    def __init__(self, env, name, ledger):
        super().__init__(env, name, ledger)

    def receive(self, entity):
        # Call base class to log ENTITY_RECEIVED
        super().receive(entity)
        
        # Log the destruction event sequentially after receipt
        self.ledger.log(
            self.env,
            entity, 
            self, 
            EventType.ENTITY_DESTROYED
        )

        self.notify_upstream_can_receive()

class Ledger:
    def __init__(self):
        self.records = []

    def log(self, env: DSEEnvironment, entity: Entity, block: Block, event_type: EventType):
        self.records.append(
            {
                'time': env.time, 
                'entity_id': entity.id,
                'entity_type': entity.type,
                'block': block.name, 
                'event': event_type
            }
        )
    
    def to_dataframe(self):
        return pd.DataFrame(self.records)


