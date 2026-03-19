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

        # Upstream round robin start index
        self._us_rr_idx = 0

        # Forward linkages
        self.next_blocks: list[Block] = []

        # Backward linkages
        self.upstream_blocks: list[Block] = []

    def connect(self, next_block: Block):
        # Forward connection
        self.next_blocks.append(next_block)
        # Backward connection
        next_block.upstream_blocks.append(self)

        # reset the round robin index 
        self._us_rr_idx = 0

    def can_receive(self, entity: Entity = None):
        # Base class can always receive
        return True
    
    def receive(self, entity: Entity):
        # First log the transaction 
        self.ledger.log(self.env, entity, self, EventType.ENTITY_RECEIVED)

        # raise NotImplementedError("This function must be implemented!")
    
    def notify_upstream_can_receive(self):
        num_upstream = len(self.upstream_blocks)
        
        # Safety check to prevent ZeroDivisionError on the modulo
        if num_upstream == 0:
            return
            
        for idx in range(num_upstream):
            # Calculate the shifted index using your round-robin offset
            target_idx = (idx + self._us_rr_idx) % num_upstream
            
            # Grab the actual block object from the list
            upstream_block = self.upstream_blocks[target_idx]
            upstream_block.handle_downstream_can_receive()

        # Increment round robin index for the next time this is called
        self._us_rr_idx = (self._us_rr_idx + 1) % num_upstream

    # Handle a downstream message
    def handle_downstream_can_receive(self):
        pass


# Generator Block
class GeneratorBlock(Block):
    def __init__(self, env: DSEEnvironment, name: str, ledger: Ledger, interarrival_dist: Sampler, log=False):
        super().__init__(env, name, ledger)
        self.interarrival_dist = interarrival_dist
        self._count = 0
        self.log = log

        # Initialise the first recursive entity generator
        # event
        self.env.add_future_event(0, self._generate)


    def _generate(self):
        entity = Entity(id=self._count, creation_time=self.env.time)

        if self.log:
            self.ledger.log(
                env=self.env,
                entity=entity,
                block=self,                    
                event_type=EventType.ENTITY_CREATED
            )

        if self.next_blocks and self.next_blocks[0].can_receive(entity):
            # No need to log creation event this is done in entity
            self.next_blocks[0].receive(entity)

        else:
            if self.log:
                self.ledger.log(
                    env=self.env,
                    entity=entity,
                    block=self,
                    event_type=EventType.ENTITY_DESTROYED
                )

        # Trigger the next creation of an entity
        self.env.add_future_event(
            dt = self.interarrival_dist.sample(),
            callback=self._generate
        )

        self._count += 1

    
# Service Block
class ServiceBlock(Block):
    def __init__(self, env, name, ledger, service_time_dist: Sampler):
        super().__init__(env, name, ledger)
        self.service_time_dist = service_time_dist
        self.is_busy = False
        self.blocked_entity: Entity = None

    def can_receive(self, entity = None):
        return not self.is_busy and self.blocked_entity is None
    
    def receive(self, entity):
        
        self.is_busy = True
        self.env.add_future_event(
            dt = self.service_time_dist.sample(),
            callback=self._finish,
            entity=entity
        )
    
    def _finish(self, entity: Entity):
        
        # if not terminated
        if not self.next_blocks:
            self.is_busy = False
            self.notify_upstream_can_receive()
            return

        next = self.next_blocks[0]

        # Try to pass entity downstream
        if next.can_receive(entity = entity):
            next.receive(entity = entity)
            self.is_busy = False
            self.notify_upstream_can_receive()
        else:
        # Unable to pass entity wait until downstream message
            self.blocked_entity = entity

    def handle_downstream_can_receive(self):
        # Downstream is ready to receive entity 
        if self.blocked_entity:

            next_block = self.next_blocks[0]

            # It is possible that another block won a race condition so check again
            if next_block.can_receive(entity = self.blocked_entity):
                
                entity_to_sent = self.blocked_entity # save entity for smooth andoff
                self.is_busy = False
                self.blocked_entity = None

                next_block.receive(entity = entity_to_sent)
                self.notify_upstream_can_receive()


# Queue Block
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
        self.fifo.append(entity)

        # special case that downstream is free
        self._try_push()

    def _try_push(self):
        # Keep trying to push as long as we have entities AND downstream blocks
        while self.fifo and self.next_blocks:
            
            entity_pushed = False
            num_downstream = len(self.next_blocks)
            
            # Round Robin through the servers to distribute the load fairly
            for idx in range(num_downstream):
                target_idx = (idx + self._ds_rr_idx) % num_downstream
                target_server = self.next_blocks[target_idx]
                
                # Check if this specific server can take the first entity
                if target_server.can_receive(self.fifo[0]):
                    
                    # 1. Pop from the FRONT of the line (index 0)
                    entity = self.fifo.popleft() 
                    
                    # 2. Edge-triggered notification (ensure variable names match!)
                    if len(self.fifo) == self.capacity - 1:
                        self.notify_upstream_can_receive()
                        
                    # 3. Send it away
                    target_server.receive(entity)
                    
                    # 4. Increment downstream round-robin index for the next item
                    self._ds_rr_idx = (target_idx + 1) % num_downstream
                    
                    entity_pushed = True
                    
                    # 5. BREAK the inner for-loop! We successfully routed this entity.
                    # This sends us back to the top of the while-loop to handle the next entity.
                    break 
            
            # If we asked every server and NOBODY had space, we are totally blocked.
            # Break the while loop to stop trying.
            if not entity_pushed:
                break

    def handle_downstream_can_receive(self):
        self._try_push()


# Destroyer Block
class DestroyerBlock(Block):
    def __init__(self, env, name, ledger):
        super().__init__(env, name, ledger)

    def receive(self, entity):
        self.ledger.log(
            self.env,
            entity, 
            self, 
            EventType.ENTITY_DESTROYED
        )

        self.notify_upstream_can_receive()

# Junction Block 
class JunctionBlock(Block):

    def __init__(self, env, name, ledger, routing_func):
        super().__init__(env, name, ledger)
        self.routing_func = routing_func

    def can_receive(self, entity = None):
        # Find the next block for the entity
        next_block = self.routing_func(entity, self.next_blocks)
        return next_block.can_receive(entity)
    
    def receive(self, entity):
        self.ledger.log(self.env, entity, self.name, "routed")
        target = self.routing_func(entity, self.next_blocks)
        target.receive(entity)

    def handle_downstream_can_receive(self):
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


