from old.WasteRecyclingZone import WasteRecyclingZone
from old.ZoneTransition import ZoneTransition
import numpy as np
from Enums import Event


class WasteRecyclingPlant:

    def __init__(self, zones: list[WasteRecyclingZone], zone_transitions: list[ZoneTransition]):
        self.zones = zones
        self.zone_transitions = zone_transitions

    def set_event_queue(self, event_queue):
        self.event_queue = event_queue

    def update(self, event: Event):
        pass
    