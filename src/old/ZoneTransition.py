from old.WasteRecyclingZone import WasteRecyclingZone

class ZoneTransition: 

    def __init__(self, origin: WasteRecyclingZone, destination: WasteRecyclingZone):
        self.origin = origin
        self.destination = destination