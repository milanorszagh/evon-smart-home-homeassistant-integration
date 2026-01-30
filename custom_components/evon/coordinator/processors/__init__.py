"""Device processors for Evon Smart Home coordinator."""

from .lights import process_lights
from .blinds import process_blinds
from .climate import process_climates
from .switches import process_switches
from .smart_meters import process_smart_meters
from .air_quality import process_air_quality
from .valves import process_valves
from .home_states import process_home_states
from .bathroom_radiators import process_bathroom_radiators
from .scenes import process_scenes

__all__ = [
    "process_lights",
    "process_blinds",
    "process_climates",
    "process_switches",
    "process_smart_meters",
    "process_air_quality",
    "process_valves",
    "process_home_states",
    "process_bathroom_radiators",
    "process_scenes",
]
