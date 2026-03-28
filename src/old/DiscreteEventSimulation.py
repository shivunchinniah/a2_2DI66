import numpy as np
from Sampler import Sampler
from collections import deque
from Enums import EventType, Event



class DiscreteEventSimulation:

    def __init__(self, 
                initial_time: np.float32,
                simulation_end_time,
                arrival_rate_distribution: Sampler, 
                waste_recycling_plant: WasteRecyclingPlant):
        self.time = initial_time
        self.simulation_end_time = simulation_end_time
        
        self.event_queue : deque[Event] = deque()
        # first customer arrives determine a random time
        dt = arrival_rate_distribution.sample()
        self.event_queue.append(Event(EventType.CUSTOMER_ARRIVES, self.time + dt))

        self.waste_recycling_plant = waste_recycling_plant
        self.waste_recycling_plant.set
    

    def run(self):

        while len(self.event_queue) >  0 and self.time < self.simulation_end_time:
            # Get the next event
            e = self.event_queue.pop()
            self.time = e.time

            self.waste_recycling_plant.update(e)
    