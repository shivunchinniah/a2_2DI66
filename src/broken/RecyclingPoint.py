from Environment import Block, Environment, Event
from scipy.stats import gamma
import numpy as np
from Distribution import Distribution
from collections import deque
import heapq
from Entity import Customer, CustomerItineraryGenerator

def GammaFunc(mean, std):
    alpha = (mean/std)**2
    beta = std**2/mean
    dist = Distribution(gamma(alpha, scale=beta))
    return dist

class ExternalQueue(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.queue = deque()

    def receive(self, entity):
        mult = self.env.customer_multiplier 
        self.queue.append(entity)
        new_entity = Customer(self.env.itinerary_gen)
        t = self.env.time
        SPH = 3600 # seconds per Hour
        hour = 9.5 + t/SPH

        if hour < 10:
            self.env.add_future_event(SPH/10/mult, 'Arrival', new_entity)
        elif hour < 10.75:
            self.env.add_future_event(SPH/100/mult, 'Arrival', new_entity)
        elif hour < 11.5:
            self.env.add_future_event(SPH/40/mult, 'Arrival', new_entity)
        elif hour < 13:
            self.env.add_future_event(SPH/100/mult, 'Arrival', new_entity)
        elif hour < 15:
            self.env.add_future_event(SPH/100/mult, 'Arrival', new_entity)
        elif hour < 16.5:
            self.env.add_future_event(SPH/80/mult, 'Arrival', new_entity)
        elif hour < 17:
            self.env.add_future_event(SPH/50/mult, 'Arrival', new_entity)
        else:
            pass

        self.move_downstream(entity)

    def move_downstream(self, entity):
        if len(self.queue) == 1:
            for block in self.next_blocks:
                if block.handle_upstream_offer(entity):
                    self.queue.popleft()
                    block.receive(entity)

    def handle_downstream_can_receive(self, block):
        if len(self.queue) >= 1:
            entity = self.queue[0]
            if block.handle_upsteam_offer(entity):
                self.queue.popleft()
                block.receive(entity)

    def can_receive(self, size):
        return True

class Entrance(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.dist = GammaFunc(30, 12)
        self.free_spaces = 2


    def receive(self, entity):
        super().receive(entity)
        self.env.add_future_event(self.dist.rvs(), 'Entrance', entity)


    def can_receive(self, size):
        if self.free_spaces == 2:
            return True
        else:
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
            
    

class HOQueue(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.free_spaces = 14
        self.queue = deque()
    
    def receive(self, entity):
        self.free_spaces -= entity.size
        self.queue.append(entity)
        self.move_downstream(entity)

    def move_downstream(self, entity):
        if len(self.queue) == 1:
            for block in self.next_blocks:
                if block.handle_upstream_offer(entity):
                    self.queue.popleft()
                    self.free_spaces += entity.size
                    block.receive(entity)
                    self.notify_upstream_can_receive()
                    break

    def handle_downstream_can_receive(self, block):
        if len(self.queue) >= 1:
            entity = self.queue[0]
            if block.handle_upsteam_offer(entity):
                self.queue.popleft()
                self.free_spaces += entity.size
                block.receive(entity)
                self.push()
                self.notify_upstream_can_receive()



    def handle_upstream_offer(self, entity):
        if self.can_receive(entity.size):
            return True
        return False


class Hall(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.distLarge = GammaFunc(423, 270)
        self.distSmall = GammaFunc(240, 150)
        self.free_spaces = 12

    def receive(self, entity):
        super().receive(entity)
        if entity.size == 1:
            self.env.add_future_event(self.distSmall.rvs(), 'Hall', entity)
        else:
            self.env.add_future_event(self.distLarge.rvs(), 'Hall', entity)

    def can_receive(self, size):
        if self.free_spaces >= size:
            if size == 1 and self.env.overflow.free_spaces >= 1:
                return False
            else:
                return True
        else:
            return False

class Overflow(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.dist = GammaFunc(180, 150)
        self.free_spaces = 10

    def receive(self, entity):
        super().receive(entity)
        self.env.add_future_event(self.dist.rvs(), 'Overflow', entity)

    def can_receive(self, size):
        if self.free_spaces >= size and size == 1:
            return True
        else:
            return False


class DcDd(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.dist = GammaFunc(331, 300)
        self.free_spaces = 7

    def receive(self, entity):
        super().receive(entity)
        self.env.add_future_event(self.dist.rvs(), 'DcDd', entity)

class Green(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.dist = GammaFunc(341, 260)
        self.free_spaces = 5

    def receive(self, entity):
        super().receive(entity)
        self.env.add_future_event(self.dist.rvs(), 'Green', entity)


class Rest(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)
        self.dist = GammaFunc(141, 36)
        self.free_spaces = 5

    def receive(self, entity):
        super().receive(entity)
        self.env.add_future_event(self.dist.rvs(), 'Rest', entity)

class Exit(Block):
    def __init__(self, name, env, ledger):
        super().__init__(name, env, ledger)

    def can_receive(self, size):
        return True



class RecyclingPointEnv(Environment):
    def __init__(self, customer_multiplier = 1):
        super().__init__()
        self.customer_multiplier = customer_multiplier
        self.itinerary_gen = CustomerItineraryGenerator()
        # Create Blocks
        # Name has to match itinerary
        self.external_queue = ExternalQueue('ExternalQueue', self, self.ledger)
        self.entrance = Entrance(0, self, self.ledger)
        self.ho_queue = HOQueue(1, self, self.ledger)
        self.hall = Hall(1, self, self.ledger)
        self.overflow = Overflow(1, self, self.ledger)
        self.dcdd = DcDd(2, self, self.ledger)
        self.green = Green(3, self, self.ledger)
        self.rest = Rest(4, self, self.ledger)
        self.exit = Exit(5, self, self.ledger)

        # Connect Blocks
        self.external_queue.connect(self.entrance)
        self.entrance.connect(self.ho_queue)
        self.ho_queue.connect(self.hall)
        self.ho_queue.connect(self.overflow)
        self.ho_queue.connect(self.dcdd)
        self.ho_queue.connect(self.green)
        self.ho_queue.connect(self.rest)
        self.hall.connect(self.dcdd)
        self.hall.connect(self.rest)
        self.hall.connect(self.exit)
        self.overflow.connect(self.dcdd)
        self.overflow.connect(self.rest)
        self.overflow.connect(self.exit)
        self.dcdd.connect(self.rest)
        self.dcdd.connect(self.exit)
        self.green.connect(self.rest)
        self.green.connect(self.exit)
        self.rest.connect(self.exit)


    def run(self, end_time):
        # add the first customer arrival event which will recursively generate more customers. 
        self.add_future_event(0, 'Arrival', Customer(self.itinerary_gen))
        
        print(self)
        while self.future_event_set and self.future_event_set[0].time < end_time:
            e = heapq.heappop(self.future_event_set)
            self.time = e.time
            print(9.5 + self.time/3600, e.typ)
            print(e.entity.id, e.entity.size, e.entity.itinerary)
            
            
            match e.typ:
                case 'Arrival':
                    self.external_queue.receive(e.entity)
                case 'Entrance':
                    self.entrance.move_downstream(e.entity)
                case 'Hall':
                    self.hall.move_downstream(e.entity)
                case 'Overflow':
                    self.overflow.move_downstream(e.entity)
                case 'DcDd':
                    self.dcdd.move_downstream(e.entity)
                case 'Green':
                    self.green.move_downstream(e.entity)
                case 'Rest':
                    self.rest.move_downstream(e.entity)
            
            print(self)
        print(9.5+ self.time/3600)


    def __str__(self):
        result = f'External Queue Length: {len(self.external_queue.queue)} \n'
        result += f'Entrance In Use: {self.entrance.free_spaces < 2}, Free Spaces: {self.entrance.free_spaces}, Waiting To Move On: {len(self.entrance.finished_entities) >0}\n'
        result += f'Hall/Overflow Queue Length: {len(self.ho_queue.queue)}, Free Spaces: {self.ho_queue.free_spaces} \n'
        result += f'Hall Free Spaces: {self.hall.free_spaces} \n'
        result += f'Overflow Free Spaces: {self.overflow.free_spaces} \n'
        result += f'Green Free Spaces: {self.green.free_spaces} \n'
        result += f'DcDd Free Spaces: {self.dcdd.free_spaces} \n'
        result += f'Rest Free Spaces: {self.rest.free_spaces} \n'

        return result





