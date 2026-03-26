from enum import Enum
from old.WasteRecyclingZone import WasteType
from Enums import VehicleSize, CustomerState
import numpy as np



class Customer: 

    def __init__(self, uid,  waste_types: list[WasteType], vehicle_size: VehicleSize, wait_time: np.float32 = 0, service_time: np.float32 = 0, initial_state: CustomerState = CustomerState.WAITING, initial_time: np.float32 = 0):
        self.waste_types = waste_types
        self.vehicle_size = vehicle_size
        self.uid = uid
        self.wait_time = wait_time
        self.service_time = service_time
        self.state = initial_state
        self.last_update_time = initial_time

    def update_state(self, state: CustomerState, time: np.float32):

        # Compute time delta
        dt = time - self.last_update_time

        # State change logic
        if self.state == CustomerState.WAITING:
            self.wait_time += dt
        elif self.state == CustomerState.SERVICE:
            self.service_time += dt 

        # Done save current state
        self.last_update_time = time
        self.state = state
