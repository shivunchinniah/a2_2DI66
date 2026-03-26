import heapq
import itertools
import random
import pandas as pd

# ==========================================
# 1. CORE ENGINE & BASE CLASSES
# ==========================================

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

# ==========================================
# 2. SPECIALIZED NODES
# ==========================================

class Generator(Node):
    def __init__(self, env, name, ledger, interarrival_func, next_node=None):
        super().__init__(env, name, ledger, next_node)
        self.interarrival_func = interarrival_func
        self._count = 0
        self.env.schedule(0, self._generate)

    def _generate(self):
        self._count += 1
        # Randomly assign a type to test the junction routing
        entity_type = random.choices(["hall_bound", "green_bound"], weights=[0.7, 0.3])[0]
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
        target_node = self.routing_func(entity)
        return target_node.can_receive(entity)

    def receive(self, entity):
        self.ledger.log(self.env.now, entity.entity_id, self.name, "routed")
        target_node = self.routing_func(entity)
        target_node.receive(entity)

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


# ==========================================
# 3. WIRING THE TOPOLOGY & RUNNING
# ==========================================

if __name__ == "__main__":
    env = Environment()
    ledger = GeneralLedger()

    # Define the routing logic for the Junction
    def routing_logic(entity):
        if entity.properties.get("type") == "green_bound":
            return green_zone
        else:
            return hall_zone

    # --- Initialize from Back to Front ---

    # 7. Sink
    sink = Destroyer(env, "Sink", ledger)

    # 6. Rest Zone (Merges DC and Green, feeds Sink)
    rest_zone = BlockedZone(env, "Rest_Zone", ledger, num_servers=4, queue_capacity=10, 
                            service_time_func=lambda: random.expovariate(1.0), next_node=sink)

    # 5. DC Zone (feeds Rest)
    dc_zone = BlockedZone(env, "DC_Zone", ledger, num_servers=2, queue_capacity=5, 
                          service_time_func=lambda: random.uniform(2, 4), next_node=rest_zone)

    # 4. Overflow Zone (feeds DC)
    overflow_zone = BlockedZone(env, "Overflow_Zone", ledger, num_servers=3, queue_capacity=8, 
                                service_time_func=lambda: random.expovariate(0.5), next_node=dc_zone)

    # 3. Branches from Junction
    # Branch A: Hall Zone (feeds Overflow)
    hall_zone = BlockedZone(env, "Hall_Zone", ledger, num_servers=5, queue_capacity=10, 
                            service_time_func=lambda: random.normalvariate(3, 0.5), next_node=overflow_zone)
    
    # Branch B: Green Zone (feeds Rest)
    green_zone = BlockedZone(env, "Green_Zone", ledger, num_servers=2, queue_capacity=5, 
                             service_time_func=lambda: random.uniform(1, 3), next_node=rest_zone)

    # 2. Junction
    junction = Junction(env, "Main_Junction", ledger, routing_func=routing_logic)
    junction.connect_downstream(hall_zone)
    junction.connect_downstream(green_zone)

    # 1. Start of pipeline: Buffer and Generator
    buffer = InfiniteBuffer(env, "Entry_Buffer", ledger, next_node=junction)
    
    gen = Generator(env, "Generator", ledger, 
                    interarrival_func=lambda: random.expovariate(2.0), # Fast arrivals to test blocking
                    next_node=buffer)

    # --- Run Simulation ---
    print("Running simulation...")
    env.run(until=100) # Run for 100 time units
    print(f"Simulation complete. {len(ledger.records)} events logged.")

    # --- Quick Data Check ---
    df = pd.DataFrame(ledger.records)
    blocked_events = df[df['event'] == 'server_blocked']
    print(f"Number of times a server was blocked: {len(blocked_events)}")