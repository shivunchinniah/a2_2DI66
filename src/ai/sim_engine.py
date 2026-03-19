import heapq
import itertools
import random
import pandas as pd

class Environment:
    def __init__(self):
        self.now = 0.0
        self.fes = []
        self._counter = itertools.count()

    def schedule(self, delay, callback, *args, **kwargs):
        heapq.heappush(self.fes, (self.now + delay, next(self._counter), callback, args, kwargs))

    def run(self, until):
        while self.fes and self.fes[0][0] <= until:
            time, _, callback, args, kwargs = heapq.heappop(self.fes)
            self.now = time
            callback(*args, **kwargs)

class GeneralLedger:
    __slots__ = ['records']
    def __init__(self):
        self.records = []

    def log(self, time, entity_id, node_name, event_type):
        self.records.append({"time": time, "entity_id": entity_id, "node": node_name, "event": event_type})

    def to_dataframe(self):
        return pd.DataFrame(self.records)

class Entity:
    __slots__ = ['entity_id', 'properties']
    def __init__(self, entity_id, properties=None):
        self.entity_id = entity_id
        self.properties = properties or {}

class Node:
    def __init__(self, env, name, ledger, next_node=None):
        self.env = env
        self.name = name
        self.ledger = ledger
        self.next_node = next_node
        self.upstream_nodes = []
        if self.next_node:
            self.next_node.upstream_nodes.append(self)

    def can_receive(self, entity): return True
    def receive(self, entity): raise NotImplementedError
    def wake_up(self): pass
    def wake_up_upstream(self):
        for node in self.upstream_nodes:
            node.wake_up()

class Generator(Node):
    def __init__(self, env, name, ledger, interarrival_func, entity_types, type_weights, next_node=None):
        super().__init__(env, name, ledger, next_node)
        self.interarrival_func = interarrival_func
        self.entity_types = entity_types
        self.type_weights = type_weights
        self._count = 0
        self.env.schedule(0, self._generate)

    def _generate(self):
        self._count += 1
        entity_type = random.choices(self.entity_types, weights=self.type_weights)[0]
        entity = Entity(f"E{self._count}", properties={"type": entity_type})
        
        self.ledger.log(self.env.now, entity.entity_id, self.name, "created")
        if self.next_node and self.next_node.can_receive(entity):
            self.next_node.receive(entity)
        else:
            self.ledger.log(self.env.now, entity.entity_id, self.name, "dropped")
            
        self.env.schedule(self.interarrival_func(), self._generate)

class InfiniteBuffer(Node):
    def __init__(self, env, name, ledger, next_node=None):
        super().__init__(env, name, ledger, next_node)
        self.queue = []

    def receive(self, entity):
        self.ledger.log(self.env.now, entity.entity_id, self.name, "buffered")
        self.queue.append(entity)
        self._try_push()

    def _try_push(self):
        while self.queue and self.next_node and self.next_node.can_receive(self.queue[0]):
            entity = self.queue.pop(0)
            self.ledger.log(self.env.now, entity.entity_id, self.name, "released_from_buffer")
            self.next_node.receive(entity)
            self.wake_up_upstream()

    def wake_up(self):
        self._try_push()

class Junction(Node):
    def __init__(self, env, name, ledger, routing_func):
        super().__init__(env, name, ledger) 
        self.routing_func = routing_func
        self.downstream_nodes = set()

    def connect_downstream(self, node):
        self.downstream_nodes.add(node)
        node.upstream_nodes.append(self)

    def can_receive(self, entity):
        return self.routing_func(entity).can_receive(entity)

    def receive(self, entity):
        self.ledger.log(self.env.now, entity.entity_id, self.name, "routed")
        self.routing_func(entity).receive(entity)

    def wake_up(self):
        self.wake_up_upstream()

class BlockedZone(Node):
    def __init__(self, env, name, ledger, num_servers, queue_capacity, service_time_func, next_node=None):
        super().__init__(env, name, ledger, next_node)
        self.num_servers = num_servers
        self.queue_capacity = queue_capacity
        self.service_time_func = service_time_func
        self.queue = []
        self.busy_servers = 0
        self.blocked_entities = []

    def can_receive(self, entity=None):
        return len(self.queue) < self.queue_capacity

    def receive(self, entity):
        self.ledger.log(self.env.now, entity.entity_id, self.name, "arrived")
        if self.busy_servers < self.num_servers:
            self.busy_servers += 1
            self._start_service(entity)
        else:
            self.queue.append(entity)
            self.ledger.log(self.env.now, entity.entity_id, self.name, "queued")

    def _start_service(self, entity):
        self.ledger.log(self.env.now, entity.entity_id, self.name, "service_started")
        self.env.schedule(self.service_time_func(), self._finish_service, entity)

    def _finish_service(self, entity):
        if self.next_node and self.next_node.can_receive(entity):
            self.ledger.log(self.env.now, entity.entity_id, self.name, "service_finished")
            self._push_downstream(entity)
        else:
            self.ledger.log(self.env.now, entity.entity_id, self.name, "server_blocked")
            self.blocked_entities.append(entity)

    def _push_downstream(self, entity):
        self.next_node.receive(entity)
        if self.queue:
            next_entity = self.queue.pop(0)
            self._start_service(next_entity)
            self.wake_up_upstream() 
        else:
            self.busy_servers -= 1

    def wake_up(self):
        entities_to_push = list(self.blocked_entities)
        self.blocked_entities.clear()
        
        for entity in entities_to_push:
            if self.next_node.can_receive(entity):
                self.ledger.log(self.env.now, entity.entity_id, self.name, "server_unblocked")
                self._push_downstream(entity)
            else:
                self.blocked_entities.append(entity)

class Destroyer(Node):
    def receive(self, entity):
        self.ledger.log(self.env.now, entity.entity_id, self.name, "destroyed")