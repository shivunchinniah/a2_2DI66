import random
from collections import deque
from DSE import Block, Entity
from Enums import EventType, EntityTypes, VehicleSize, WasteType

from CustomerWithItinerary import CustomerItineraryGenerator, Customer

class CustomerEntity(Entity):
    __slots__ = ['vehicle_size', 'waste_types', 'flags']
    def __init__(self, id, creation_time, vehicle_size, waste_types):
        super().__init__(id, creation_time, EntityTypes.CUSTOMER)
        self.vehicle_size = vehicle_size
        self.waste_types = waste_types
        self.flags = {} # Used to track if they bypassed a zone

class WRPGeneratorBlock(Block):
    def __init__(self, env, name, ledger, interarrival_dist, log=False):
        super().__init__(env, name, ledger)
        self.interarrival_dist = interarrival_dist
        self._count = 0
        self.log = log
        self.env.add_future_event(0, self._generate)

    def _generate(self):
        v_size = VehicleSize.BIG if random.random() < 0.2 else VehicleSize.SMALL
        if random.random() < 0.3:
            w_types = [WasteType.TYPE_A]
            if random.random() < 0.5: w_types.append(WasteType.TYPE_REST)
        else:
            w_types = [WasteType.TYPE_B]
            if random.random() < 0.4: w_types.append(WasteType.TYPE_DCDD)
            if random.random() < 0.3: w_types.append(WasteType.TYPE_REST)

        entity = CustomerEntity(self._count, self.env.time, v_size, w_types)

        if self.log:
            self.ledger.log(self.env, entity, self, EventType.ENTITY_CREATED)

        if self.next_blocks and self.next_blocks[0].can_receive(entity):
            self.next_blocks[0].receive(entity)
        else:
            if self.log:
                self.ledger.log(self.env, entity, self, EventType.ENTITY_DESTROYED)

        # Safely schedule the next arrival
        self.env.add_future_event(self.interarrival_dist.sample(), self._generate)
        self._count += 1

class WRPZoneBlock(Block):
    def __init__(self, env, name, ledger, total_bays, queue_limit, service_time_dist, bypass_func=None, routing_func=None):
        super().__init__(env, name, ledger)
        self.total_bays = total_bays
        self.queue_limit = queue_limit
        self.service_time_dist = service_time_dist
        self.bypass_func = bypass_func
        self.routing_func = routing_func # Added to handle multi-exit zones
        
        self.available_bays = total_bays
        self.fifo = deque()
        self.blocked_entities = [] 

    def _get_capacity_cost(self, entity):
        if self.bypass_func and self.bypass_func(entity):
            return 0
        cost = 2 if entity.vehicle_size == VehicleSize.BIG else 1
        return min(cost, self.total_bays)

    def can_receive(self, entity=None):
        # 1. Check if there is physical queue space
        if len(self.fifo) < self.queue_limit:
            return True
            
        # 2. If queue is 0, evaluate if a bay can be seized immediately
        cost = self._get_capacity_cost(entity) if entity else 1
        if self.available_bays >= cost and len(self.fifo) == 0:
            return True
            
        return False
        
    def receive(self, entity):
        super().receive(entity)
        self.fifo.append(entity)
        self._try_service()

    def _try_service(self):
        while self.fifo:
            entity = self.fifo[0]
            is_bypassing = self.bypass_func and self.bypass_func(entity)
            cost = self._get_capacity_cost(entity)
            
            if self.available_bays >= cost:
                self.fifo.popleft()
                self.available_bays -= cost
                self.ledger.log(self.env, entity, self, EventType.SERVICE_STARTED)
                
                if is_bypassing:
                    entity.flags[f'bypassed_{self.name}'] = True
                    st = 10.0 
                else:
                    st = self.service_time_dist.sample()
                    # Mark visited to prevent infinite routing loops downstream
                    entity.flags[f'visited_{self.name}'] = True 
                    
                self.env.add_future_event(st, self._finish_service, entity=entity, cost=cost)
                self.notify_upstream_can_receive()
            else:
                break
                
    def _finish_service(self, entity, cost):
        self.ledger.log(self.env, entity, self, EventType.SERVICE_COMPLETED)
        if not self.next_blocks:
            self.available_bays += cost
            self._try_service()
            return
            
        # Dynamically determine the next block
        if self.routing_func:
            next_block = self.routing_func(entity, self.next_blocks)
        else:
            next_block = self.next_blocks[0]
            
        if next_block.can_receive(entity):
            self.available_bays += cost
            next_block.receive(entity)
            self._try_service()
        else:
            # Bind the target block to the blocked entity for later evaluation
            self.blocked_entities.append((entity, cost, next_block))
            
    def handle_downstream_can_receive(self):
        movable_entities = []
        remaining_entities = []
        
        # 1. Identify which entities can move and which are still blocked
        for item in self.blocked_entities:
            entity, cost, next_block = item
            if next_block.can_receive(entity):
                movable_entities.append(item)
            else:
                remaining_entities.append(item)
                
        if not movable_entities:
            return
            
        # 2. Mutate state BEFORE triggering downstream events to prevent recursive crashes
        self.blocked_entities = remaining_entities
        
        # 3. Now safely push entities downstream
        for item in movable_entities:
            entity, cost, next_block = item
            self.available_bays += cost
            next_block.receive(entity)
            
        # 4. Pull new entities from the queue if bays were freed
        self._try_service()

class JunctionBlock(Block):
    def __init__(self, env, name, ledger, routing_func):
        super().__init__(env, name, ledger)
        self.routing_func = routing_func

    def can_receive(self, entity = None):
        next_block = self.routing_func(entity, self.next_blocks)
        return next_block.can_receive(entity)
    
    def receive(self, entity):
        super().receive(entity)
        self.ledger.log(self.env, entity, self, EventType.ENTITY_ROUTED)
        target = self.routing_func(entity, self.next_blocks)
        target.receive(entity)

    def handle_downstream_can_receive(self):
        self.notify_upstream_can_receive()

class DestroyerBlock(Block):
    def __init__(self, env, name, ledger):
        super().__init__(env, name, ledger)

    def receive(self, entity):
        super().receive(entity)
        self.ledger.log(self.env, entity, self, EventType.ENTITY_DESTROYED)
        self.notify_upstream_can_receive()