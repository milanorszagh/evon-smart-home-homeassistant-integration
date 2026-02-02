"""Device processors for Evon Smart Home coordinator."""

from .air_quality import process_air_quality
from .bathroom_radiators import process_bathroom_radiators
from .blinds import process_blinds
from .cameras import process_cameras
from .climate import process_climates
from .home_states import process_home_states
from .intercoms import process_intercoms
from .lights import process_lights
from .scenes import process_scenes
from .security_doors import process_security_doors
from .smart_meters import process_smart_meters
from .switches import process_switches
from .valves import process_valves

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
    "process_security_doors",
    "process_intercoms",
    "process_cameras",
]
