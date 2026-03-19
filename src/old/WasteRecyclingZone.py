from Sampler import Sampler
from collections import deque
from Customer import Customer
from Enums import WasteType, VehicleSize, Event, EventType
import numpy as np







class WasteRecyclingZone:

    def __init__(self, name: str, supported_waste_types: list[WasteType], queue_size: int, parking_bays: int, parking_bay_pairs: list[tuple[int, int]], service_time_distribution: Sampler):
        self.name = name
        self.supported_waste_types = supported_waste_types
        self.queue_size = queue_size
        self.parking_bays_size = parking_bays
        self.parking_bay_pairs = parking_bay_pairs
        self.service_time_distribution = service_time_distribution

        self.queue = deque() 

        self.parking_bays = np.array([False] * self.parking_bays_size)
        self.leaveQueue



    def set_event_queue(self, event_queue):
        self.event_queue = event_queue

    # This update is only called if the customer is interacting with this queue
    def update(self, event: Event):
        
        # Event handler 
        if event == EventType.CUSTOMER_ARRIVES_QUEUE:
            self.handle_customer_arrives_queue(event)
        elif event == EventType.CUSTOMER_LEAVES_QUEUE_BEGINS_SERVICE:
            self.handle_customer_leaves_queue_begins_service(event)

    def handle_customer_arrives_queue(self, event: Event):
        pass

    def handle_customer_leaves_queue_begins_service(self, event: Event):
        pass


    def service_or_fail(self, customer: Customer):
        
        # fill the first available parking bay 
        idx = -1

        if customer.vehicle_size == VehicleSize.SMALL:
            available_bays = np.where(self.parking_bays)

            if available_bays > 0: 
                pass
                
                
                
            else:
                return False
        elif customer.vehicle_size == VehicleSize.BIG:
            double_bays = np.array([self.parking_bays[pair[0]] and self.parking_bays[pair[1]] for pair in self.parking_bay_pairs])
            available_pair_bays = np.where(double_bays)

            if available_pair_bays > 0:
                pass
            else:
                return False
            
    def _service(self, customer: Customer):
        pass 
