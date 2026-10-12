"""Location of camera recordings on disk.

Home Assistant's media browser ("My media") roots at ``hass.config.media_dirs["local"]``:
``/media`` on Home Assistant OS and Docker, ``<config>/media`` on venv installs.
Recordings must be written there so the Lovelace card's "All Recordings" link
(``media-source://media_source/local/evon_recordings``) finds them. Versions
before 1.23.0 always wrote to ``<config>/media/evon_recordings``; on HAOS that is
a different folder, so existing files are moved once at setup.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from homeassistant.core import HomeAssistant

from .const import RECORDING_MEDIA_DIR

_LOGGER = logging.getLogger(__name__)


def recordings_dir(hass: HomeAssistant) -> Path:
    """Return the recordings folder inside HA's local media directory."""
    media_dirs = getattr(hass.config, "media_dirs", None)
    local = media_dirs.get("local") if isinstance(media_dirs, dict) else None
    base = Path(local) if local else Path(hass.config.path("media"))
    return base / RECORDING_MEDIA_DIR


def legacy_recordings_dir(hass: HomeAssistant) -> Path:
    """Return the pre-1.23.0 location (``<config>/media/evon_recordings``)."""
    return Path(hass.config.path("media")) / RECORDING_MEDIA_DIR


def prepare_recordings_dir(hass: HomeAssistant) -> Path:
    """Create the recordings folder and migrate legacy files into it.

    Blocking (filesystem); run in an executor. Files that already exist at the
    new location are left alone on both sides.
    """
    target = recordings_dir(hass)
    target.mkdir(parents=True, exist_ok=True)

    legacy = legacy_recordings_dir(hass)
    if not legacy.is_dir() or legacy.resolve() == target.resolve():
        return target

    moved = 0
    for entry in sorted(legacy.iterdir()):
        destination = target / entry.name
        if destination.exists():
            _LOGGER.warning("Not migrating %s: %s already exists", entry, destination)
            continue
        shutil.move(str(entry), str(destination))
        moved += 1
    if moved:
        _LOGGER.info("Moved %d camera recording(s) from %s to %s", moved, legacy, target)
    return target
