from old.DSE import Block, QueueBlock, ServiceBlock, JunctionBlock, DestroyerBlock, GeneratorBlock, Entity, CustomerEntity
from Enums import EntityTypes, VehicleSize



class CustomerEntity(Entity):
    __slots__ = ['vehicle_size', 'waste_types', 'flags']
    def __init__(self, id, creation_time, vehicle_size, waste_types):
        super().__init__(id, creation_time, EntityTypes.CUSTOMER)
        self.vehicle_size = vehicle_size
        self.waste_types = waste_types
        self.flags = {} # Used to track if they bypassed a zone





class HallOverflowServiceBlock(ServiceBlock):
    def __init__(self, env, name, ledger, service_time_dist):
        super().__init__(env, name, ledger, service_time_dist)
        self._max_capacity = 2
        self.capacity = 0 # initial capacity

    def can_receive(self, entity: CustomerEntity):
        
        if entity.vehicle_size == VehicleSize.BIG: 
            return self.capacity == 0
        else:
            return self.capacity < self._max_capacity