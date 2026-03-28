import heapq


class Event():
    def __init__(self, event_time, typ, entity):
        self.time = event_time
        self.typ = typ
        self.entity = entity

    def __lt__(self, other: 'Event') -> bool:
        return self.time < other.time


class Environment: 
    def __init__(self):
        self.time = 0.0
        self.future_event_set: list[Event] = []
        self.eid = 0
        self.ledger = Ledger()

    def add_future_event(self, dt, typ, entity):
        event_time = self.time + dt
        e = Event(event_time, typ, entity)
        heapq.heappush(self.future_event_set, e)

    def run(self, end_time):
        while self.future_event_set and self.future_event_set[0].time < end_time:
            e = heapq.heappop(self.future_event_set)
            self.time = e.time
            

class Ledger:
    def __init__(self):
        self.records = []

    def log(self, env: Environment, entity, block: 'Block'):
        self.records.append({
            'time': env.time, 
            #'entity_id': entity.id,
            #'entity_type': entity.type.name if hasattr(entity.type, 'name') else entity.type,
            'block': block.name, 
            #'event': event_type.name
        })
    
    #def to_dataframe(self):
    #    return pd.DataFrame(self.records)

class Block:
    def __init__(self, name, env: Environment, ledger: Ledger):
        self.env = env
        self.name = name
        self.ledger = ledger
        self._us_rr_idx = 0
        self.next_blocks: list['Block'] = []
        self.upstream_blocks: list['Block'] = []
        self.free_spaces = 1
        self.finished_entities = []

    def connect(self, next_block: 'Block'):
        self.next_blocks.append(next_block)
        next_block.upstream_blocks.append(self)
        self._us_rr_idx = 0


    def can_receive(self, size):
        if self.free_spaces >= size:
            return True
        else:
            return False
    
    def receive(self, entity: Entity):
        self.free_spaces -= entity.size
        entity.MoveToDestination()


        #self.ledger.log(self.env, entity, self, EventType.ENTITY_RECEIVED)
    
    def notify_upstream_can_receive(self):
        num_upstream = len(self.upstream_blocks)
        if num_upstream == 0:
            return
        for idx in range(num_upstream):
            target_idx = (idx + self._us_rr_idx) % num_upstream
            upstream_block = self.upstream_blocks[target_idx]
            upstream_block.handle_downstream_can_receive(block=self)
        self._us_rr_idx = (self._us_rr_idx + 1) % num_upstream

    def handle_downstream_can_receive(self, block):
        moved_entity = False
        for idx, entity in enumerate(self.finished_entities.copy()):
            if block.handle_upsteam_offer(entity):
                self.free_spaces += entity.size
                self.finished_entities.pop(idx)
                block.receive(entity)
                moved_entity = True
                break

        if moved_entity:
            self.notify_upstream_can_receive()
            self.push()

    def push(self):
        for block in self.next_blocks:
            self.handle_downstream_can_receive(block)

    def handle_upstream_offer(self, entity):
        if entity.Destination() == self.name:
            if self.can_receive(entity.size):
                return True
        return False
            
    
    def move_downstream(self, entity):
        for block in self.next_blocks:
            if block.handle_upstream_offer(entity):
                self.free_spaces += entity.size
                block.receive(entity)
                self.notify_upstream_can_receive()
                break
        else:
            self.finished_entities.append(entity)