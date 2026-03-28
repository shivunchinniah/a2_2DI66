from __future__ import annotations
import numpy as np
from collections import deque
import heapq
from enum import Enum 


class VehicleSize(Enum):
    SMALL = 0
    BIG = 1

class LocationType(Enum):
    MAIN_QUEUE = 0
    HALL_QUEUE = 1
    HALL_OVERFLOW = 2
    DCDD = 3
    GREEN = 4
    REST = 5
    EXIT = 6

class EventType(Enum):
    BEGIN_LOCATION_ACTIVITY = 0 # Begin waiting in Queue or Begin Service
    END_LOCATION_ACTIVITY = 1 # End waiting in queue or end service
    BEGIN_WAIT_DOWNSTREAM = 2 # Waiting for downstream 
    END_WAIT_DOWNSTREAM = 3 # Done Waiting for downstream same handling as End location activity 


class Event():
    _id_count = 0
    def __init__(self, time, typ: EventType, location: Location, customer: Customer, bias=0):
        self.id = Event._id_count
        Event._id_count += 1
        self.time = time
        self.typ = typ
        self.customer = customer
        self.location = location
        self.bias = bias

    def __lt__(self, other: 'Event') -> bool:
        if self.time == other.time:
            if self.bias == other.bias:
                return self.id < other.id # Uses ID if time and bias are equal
            return self.bias < other.bias
        return self.time < other.time

class ItineraryItem:
    def __init__(self, location: LocationType, start_time = 0, end_time = 0, time_waiting = 0, service_time = 0):
        self.location = location
        # self.time = time
        self.start_time = start_time
        self.end_time = end_time
        self.time_waiting = time_waiting
        self.service_time = service_time

class Customer:
    def __init__(self, itinerary: list[ItineraryItem], vehicle_size: VehicleSize):
        self.itinerary  = itinerary
        self.itinerary_index = -1
        self.vehicle_size = vehicle_size

    def next_itinerary_item(self):  
        if self.itinerary_index + 1 < len(self.itinerary):
            return self.itinerary[self.itinerary_index + 1] 
        else: 
            return None
        
    def current_itinerary_item(self):
        if self.itinerary_index < len(self.itinerary) and self.itinerary_index >= 0:
            return self.itinerary[self.itinerary_index]
        else:
            return None
    
    def progress_itinerary(self, e: Event):
        if len(self.itinerary) > self.itinerary_index:
            current = self.current_itinerary_item()
            if current: 
                current.end_time = e.time
            self.itinerary_index += 1

            new_current = self.current_itinerary_item()
            if new_current:
             new_current.start_time = e.time




# class Ledger:
#     def __init__(self):
#         self.records = []

#     def log(self, env: Environment, entity, block: 'Block'):
#         self.records.append({
#             'time': env.time, 
#             'entity_id': entity.id,
#             #'entity_type': entity.type.name if hasattr(entity.type, 'name') else entity.type,
#             'block': block.name, 
#             'event': event_type.name
#         })
    
#     #def to_dataframe(self):
    #    return pd.DataFrame(self.records)

class Location:
    def __init__(self, name: LocationType, max_capacity: int, current_capacity:int = 0):
        self.name = name
        self.upstream_locations: list[Location] = []
        self.downstream_locations: list[Location] = []
        
        # in a Queue Location this is the actual queue
        # in a service location this the the customers who are done service and 
        # are waiting for a downstream location to become free
        self.waiting_customers: deque = deque()

        self.current_capacity = current_capacity
        self.max_capacity = max_capacity
    
    def can_receive(self, e: Event) -> bool:
        return True

    def try_receive(self, e: Event) -> bool:
        e.customer.progress_itinerary(e)
        if e.customer.vehicle_size == VehicleSize.BIG:
            self.current_capacity += 2
        else:
            self.current_capacity += 1
        return True
    
    def remove_customer(self, e: Event):
        customer = e.customer
        # remove customer from the waiting queue if they are at the front        
        if customer in self.waiting_customers:
            current_itinerary = customer.current_itinerary_item()
            current_itinerary.time_waiting = e.time - current_itinerary.end_time
            self.waiting_customers.remove(customer)

        # remove customer from capacity
        if customer.vehicle_size == VehicleSize.BIG:
            self.current_capacity -= 2
        else: # small vehicle
            self.current_capacity -=1

    def connect(self, downstream_location: Location):
        # connect for this location 
        self.downstream_locations.append(downstream_location)
        # connect the downstream location to this one
        downstream_location.upstream_locations.append(self)

    def _try_push_customer(self, e: Event):
        new_events = []
        for location in self.downstream_locations:
            if location.can_receive(e):
                
                # remove customer 
                self.remove_customer(e)
                # push downstream
                location.try_receive(e)

                customer_forwarded_event = Event(e.time, EventType.BEGIN_LOCATION_ACTIVITY, location, e.customer)
                new_events.append(customer_forwarded_event)

                # Cascade let all waiting customers know of a free spot
                if len(self.waiting_customers) > 0:
                    next_customer = self.waiting_customers[0]
                    new_events.append(Event(e.time, EventType.END_WAIT_DOWNSTREAM, self, next_customer, 0))

                # let the upstream locations know that there is a free spot
                for priority, upstream_location in enumerate(self.upstream_locations):
                    if len(upstream_location.waiting_customers) > 0:
                        upstream_customer = upstream_location.waiting_customers[0] 
                        new_events.append(Event(e.time, EventType.END_WAIT_DOWNSTREAM, upstream_location, upstream_customer, priority))
                
                break # Stop checking other downstream locations
        return new_events

    def handle_event(self, e: Event) -> list[Event]:
        # nothing to do this should be 
        return []

# Begin service --> End Service --> Go to next location
#                              |--> Begin Waiting for next location 
class ServiceLocation(Location):
    def __init__(self, name, max_capacity: int, current_capacity:int = 0,  single_bays: int = 0, single_bay_pairs: list[list[int]] = []):
        super().__init__(name, max_capacity, current_capacity)
        self.single_bays = single_bays
        self.single_bay_pairs = single_bay_pairs # to store big vehicles
        self._occupied_bays = np.array([None] * single_bays)

    def _next_free_bay(self, big_vehicle=False) -> int:
       
        if big_vehicle:
            if self.current_capacity + 2 <= self.max_capacity:
                for idx, (a, b) in enumerate(self.single_bay_pairs):
                    if not self._occupied_bays[a] and not self._occupied_bays[b]:
                        return idx
        else: # small vehicle
            if self.current_capacity + 1 <= self.max_capacity:  
                for idx in range(self.single_bays):
                    if not self._occupied_bays[idx]:
                        return idx
        
        # No free bays
        return -1
            

    def can_receive(self, e: Event) -> bool:
        customer = e.customer
        itinerary_item = customer.next_itinerary_item()
        
        if itinerary_item and itinerary_item.location == self.name: 

            big_vehicle = customer.vehicle_size == VehicleSize.BIG
            idx = self._next_free_bay(big_vehicle)
            if idx >= 0:
                return True
            else:
                return False
        
        else: # This customer is not meant to come here
            return False
            
    def try_receive(self, e: Event):
        customer = e.customer
        itinerary_item = customer.next_itinerary_item()
        
        if itinerary_item and itinerary_item.location == self.name: 

            big_vehicle = customer.vehicle_size == VehicleSize.BIG
            idx = self._next_free_bay(big_vehicle)

            if idx >= 0:
                # Take on the customer 
                customer.progress_itinerary(e)

                # adjust capacity 
                self.current_capacity += 2 if big_vehicle else 1
                # store the customer at the bay
                if big_vehicle:
                    a, b = self.single_bay_pairs[idx]
                    self._occupied_bays[a] = customer
                    self._occupied_bays[b] = customer
                else:
                    self._occupied_bays[idx] = customer

                return True

            else:
                return False
        
        else: # This customer is not meant to come here
            return False

    

    def remove_customer(self, e: Event):
        customer = e.customer
        # remove customer capacity and if they are in the waiting queue
        super().remove_customer(e)
        
        # find the customer 
        if customer.vehicle_size == VehicleSize.BIG:
            for a, b in self.single_bay_pairs:
                if self._occupied_bays[a] == customer:
                    self._occupied_bays[a] = None
                    self._occupied_bays[b] = None
                    return 
        else: # small vehicle
            for idx in range(self.single_bays):
                if self._occupied_bays[idx] == customer:
                    self._occupied_bays[idx] = None
                    return



    def handle_event(self, e: Event):
        
        new_events = []

        match(e.typ):
            case EventType.BEGIN_LOCATION_ACTIVITY : 
                # update the customer states
                itinerary_item = e.customer.current_itinerary_item()

                # generate the end service event based on the predetermined 
                # service time for the current itinerary 
                new_event = Event(
                    time=(e.time + itinerary_item.service_time), 
                    typ=EventType.END_LOCATION_ACTIVITY,
                    location=self,
                    customer=e.customer
                )
                
                new_events.append(new_event)

            case EventType.END_LOCATION_ACTIVITY:
                events = self._try_push_customer(e)
                
                # Only add to waiting list if it's their FIRST time failing to push
                if len(events) == 0: 
                   new_events.append(Event(e.time, EventType.BEGIN_WAIT_DOWNSTREAM, self, e.customer))
                new_events += events

            case EventType.END_WAIT_DOWNSTREAM: 
                # Just try to push. If it fails, do nothing! (They are already safely in the waiting list)
                new_events += self._try_push_customer(e)

            case EventType.BEGIN_WAIT_DOWNSTREAM:
                # update the end time for computing the wait time
                e.customer.current_itinerary_item().end_time = e.time
                # move the customer to the blocked
                self.waiting_customers.append(e.customer)
        
        return new_events


class QueueLocation(Location):
    def __init__(self, name, maximum_capacity, current_capacity = 0):
        super().__init__(name, maximum_capacity, current_capacity)

    def can_receive(self, e: Event) -> bool:
        customer = e.customer

        itinerary_item = customer.next_itinerary_item()
        
        if itinerary_item and itinerary_item.location == self.name: 

            big_vehicle = customer.vehicle_size == VehicleSize.BIG
            
            future_capacity = self.current_capacity
            future_capacity += 2 if big_vehicle else 1

            if future_capacity <= self.max_capacity:    
                return True

            else:
                return False
        
        else: # This customer is not meant to come here
            return False

    def try_receive(self, e: Event) -> bool:
        customer = e.customer

        itinerary_item = customer.next_itinerary_item()
        
        if itinerary_item and itinerary_item.location == self.name: 

            big_vehicle = customer.vehicle_size == VehicleSize.BIG
            
            future_capacity = self.current_capacity
            future_capacity += 2 if big_vehicle else 1

            if future_capacity <= self.max_capacity: 
                # Take on the customer 
                customer.progress_itinerary(e)
                # adjust capacity 
                self.current_capacity = future_capacity       
                return True

            else:
                return False
        
        else: # This customer is not meant to come here
            return False

    def handle_event(self, e: Event):
        

        new_events = []

        match(e.typ):

            case EventType.BEGIN_LOCATION_ACTIVITY:
                if e.customer.itinerary_index == -1:
                    self.try_receive(e)
                
                itinerary_item = e.customer.current_itinerary_item()
                
                # If queue is empty, they are the first to try to leave
                if len(self.waiting_customers) == 0:
                    # Attempt to push immediately
                    events = self._try_push_customer(e)
                    if len(events) == 0:
                        # Could not push? Add to waiting and set start wait time
                        itinerary_item.end_time = e.time
                        self.waiting_customers.append(e.customer)
                    else:
                        new_events += events
                else:
                    itinerary_item.end_time = e.time
                    self.waiting_customers.append(e.customer)

            # case EventType.BEGIN_LOCATION_ACTIVITY:
                
            #     if e.customer.itinerary_index == -1:
            #         self.try_receive(e)
                
            #      # update the customer states
            #     itinerary_item = e.customer.current_itinerary_item()
            #     # customer has arrived and they already trying to leave, special case for when the queue was empty
            #     if len(self.waiting_customers) == 0:
            #         new_events.append(Event(e.time, EventType.END_LOCATION_ACTIVITY, self, e.customer))
            #     else:
            #         # update the end time for computing the wait time
            #         itinerary_item.end_time = e.time
            #         # move the customer to the blocked
            #         self.waiting_customers.append(e.customer)

            # case EventType.END_LOCATION_ACTIVITY | EventType.END_WAIT_DOWNSTREAM:
            #     # try forwarding the customer to the next location 
            #     events = self._try_push_customer(e)

            #     # customer was successfully forwarded if events were created
            #     customer_forwarded = len(events) > 0

            #     # Could not directly forward the customer so the customer is blocking / waiting
            #     if not customer_forwarded: 
            #        # create an event to add the customer to the waiting downstream queue
            #        new_events.append(Event(e.time, EventType.BEGIN_WAIT_DOWNSTREAM, self, e.customer))

            #     new_events += events
            case EventType.END_LOCATION_ACTIVITY:
                events = self._try_push_customer(e)
                
                if len(events) == 0: 
                   new_events.append(Event(e.time, EventType.BEGIN_WAIT_DOWNSTREAM, self, e.customer))
                new_events += events



            case EventType.END_WAIT_DOWNSTREAM: 
                # This will try to push customers if they can when a downstream space becomes free
                new_events += self._try_push_customer(e)

            case EventType.BEGIN_WAIT_DOWNSTREAM:
                # update the end time for computing the wait time
                e.customer.current_itinerary_item().end_time = e.time
                # move the customer to the blocked
                self.waiting_customers.append(e.customer)

        return new_events

    




class Environment: 
    def __init__(self, customers: list[Customer], locations: dict[LocationType, Location],  initial_time):
        '''
        Parameter: 
            customers - a list of customers with pre-loaded itineraries 
            location - a dictionary of pre connected locations mapped by the location type
            initial_time - start time of the simulation 
                            '''
        
        self.time = 0.0 # Initially keep this zero
        self.future_event_set: list[Event] = []
        self.eid = 0
        # self.ledger = Ledger()
        self.locations = locations
        self.customers = customers

        # populate the customer joining the first queue in FES
        for customer in self.customers:
            
            itinerary_item = customer.next_itinerary_item()
            if itinerary_item and itinerary_item.location == LocationType.MAIN_QUEUE:
                first_loc = self.locations[LocationType.MAIN_QUEUE]
                first_event = Event(itinerary_item.start_time, EventType.BEGIN_LOCATION_ACTIVITY, first_loc, customer)
                
                self.add_future_event(first_event)

       

        # after customer arrival events set time to initial time
        self.time = initial_time
            

    def add_future_event(self, event: Event):
        heapq.heappush(self.future_event_set, event)

    def run(self, end_time):
        while self.future_event_set and self.future_event_set[0].time < end_time:
            e = heapq.heappop(self.future_event_set)
            self.time = e.time

            # Call the event handler for the location 
            new_events = self.locations[e.location.name].handle_event(e)
            for new_event in new_events:
                self.add_future_event(new_event)

    def run_with_diagnostics(env, max_steps=1000):
        print(f"{'Time':<10} | {'Event Type':<25} | {'Location':<15} | {'Queue Sizes'}")
        print("-" * 80)

        steps = 0
        while env.future_event_set and steps < max_steps:
            e = heapq.heappop(env.future_event_set)
            env.time = e.time
            
            # Log the state
            q_info = " ".join([f"{loc.name.name}:{len(loc.waiting_customers)}" for loc in env.locations.values()])
            print(f"{e.time:<10.2f} | {e.typ.name:<25} | {e.location.name.name:<15} | {q_info}")
            
            # Handle the event
            new_events = env.locations[e.location.name].handle_event(e)
            for ne in new_events:
                env.add_future_event(ne)
                
            steps += 1
            
        if steps >= max_steps:
            print("\n!!! DIAGNOSTIC ALERT: Simulation might be in an infinite loop at time", env.time)
            print("Last Event Location:", e.location.name.name)
            print("Current Customer Itinerary Index:", e.customer.itinerary_index)

# Usage:
# env = setup_environment(baseline_customers)
# run_with_diagnostics(env, max_steps=500)


if __name__ == "__main__":
    # 1. Create Itineraries
    itin1 = [
        ItineraryItem(LocationType.MAIN_QUEUE), 
        ItineraryItem(LocationType.DCDD, service_time=5), 
        ItineraryItem(LocationType.EXIT)
    ]
    itin2 = [
        ItineraryItem(LocationType.MAIN_QUEUE, start_time=2), 
        ItineraryItem(LocationType.DCDD, service_time=10), 
        ItineraryItem(LocationType.EXIT)
    ]
    
    # 2. Create Customers (1 Small, 1 Big)
    c1 = Customer(itin1, VehicleSize.SMALL)
    c2 = Customer(itin2, VehicleSize.BIG)
    
    # 3. Create Locations
    main_q = QueueLocation(LocationType.MAIN_QUEUE, maximum_capacity=10)
    # DCDD has 2 single bays (paired for big vehicles)
    dcdd = ServiceLocation(LocationType.DCDD, max_capacity=2, single_bays=2, single_bay_pairs=[[0, 1]])
    exit_loc = Location(LocationType.EXIT, max_capacity=999) 
    
    # 4. Connect Routing
    main_q.connect(dcdd)
    dcdd.connect(exit_loc)
    
    locations = {
        LocationType.MAIN_QUEUE: main_q,
        LocationType.DCDD: dcdd,
        LocationType.EXIT: exit_loc
    }
    
    # 5. Run Environment
    print("--- Starting Simulation ---")
    env = Environment([c1, c2], locations, initial_time=0)
    env.run(end_time=100)
    
    # 6. Print Results
    print("\n--- Simulation Complete ---")
    for i, c in enumerate([c1, c2]):
        print(f"\nCustomer {i+1} ({c.vehicle_size.name}) Itinerary Trace:")
        for item in c.itinerary:
            print(f"  [{item.location.name}] Start: {item.start_time:<4} | End: {item.end_time:<4} | Wait: {item.time_waiting}")