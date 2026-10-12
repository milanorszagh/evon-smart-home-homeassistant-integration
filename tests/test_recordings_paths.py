"""Tests for the recordings directory helper (no HA framework required).

Home Assistant's media browser ("My media") roots at ``hass.config.media_dirs["local"]``:
``/media`` on Home Assistant OS and Docker, ``<config>/media`` on venv installs.
Recordings must land there, or the card's "All Recordings" link browses an empty
folder on HAOS. Existing recordings from the old ``<config>/media`` location are
moved once.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from custom_components.evon.recordings import (
    legacy_recordings_dir,
    prepare_recordings_dir,
    recordings_dir,
)


def _hass(config_dir: Path, media_dirs=None):
    hass = MagicMock()
    hass.config.path = MagicMock(side_effect=lambda *parts: str(config_dir.joinpath(*parts)))
    hass.config.media_dirs = media_dirs
    return hass


def test_uses_local_media_dir_when_configured(tmp_path):
    hass = _hass(tmp_path / "config", {"local": str(tmp_path / "media")})
    assert recordings_dir(hass) == tmp_path / "media" / "evon_recordings"


def test_falls_back_to_config_media_without_local_media_dir(tmp_path):
    hass = _hass(tmp_path / "config", {})
    assert recordings_dir(hass) == tmp_path / "config" / "media" / "evon_recordings"


def test_falls_back_when_media_dirs_is_not_a_dict(tmp_path):
    """Unit tests build hass with MagicMock; treat anything that is not a dict as unset."""
    hass = _hass(tmp_path / "config", MagicMock())
    assert recordings_dir(hass) == tmp_path / "config" / "media" / "evon_recordings"


def test_legacy_dir_is_config_media(tmp_path):
    hass = _hass(tmp_path / "config", {"local": str(tmp_path / "media")})
    assert legacy_recordings_dir(hass) == tmp_path / "config" / "media" / "evon_recordings"


def test_prepare_creates_target_and_migrates_legacy_recordings(tmp_path):
    hass = _hass(tmp_path / "config", {"local": str(tmp_path / "media")})
    legacy = tmp_path / "config" / "media" / "evon_recordings"
    (legacy / "cam_20260101_120000").mkdir(parents=True)  # a JPEG-frames folder
    (legacy / "cam_20260101_120000.mp4").write_bytes(b"a")
    (legacy / "cam_20260102_120000.mp4").write_bytes(b"b")
    (legacy / "cam_20260101_120000" / "frame_0001.jpg").write_bytes(b"j")

    target = prepare_recordings_dir(hass)

    assert target == tmp_path / "media" / "evon_recordings"
    assert (target / "cam_20260101_120000.mp4").read_bytes() == b"a"
    assert (target / "cam_20260102_120000.mp4").read_bytes() == b"b"
    assert (target / "cam_20260101_120000" / "frame_0001.jpg").read_bytes() == b"j"
    assert not any(legacy.iterdir()), "legacy folder should be empty after migration"


def test_prepare_keeps_existing_target_files_on_name_clash(tmp_path):
    hass = _hass(tmp_path / "config", {"local": str(tmp_path / "media")})
    legacy = tmp_path / "config" / "media" / "evon_recordings"
    target = tmp_path / "media" / "evon_recordings"
    legacy.mkdir(parents=True)
    target.mkdir(parents=True)
    (legacy / "same.mp4").write_bytes(b"legacy")
    (target / "same.mp4").write_bytes(b"target")

    prepare_recordings_dir(hass)

    assert (target / "same.mp4").read_bytes() == b"target"
    assert (legacy / "same.mp4").read_bytes() == b"legacy"


def test_prepare_is_noop_when_legacy_is_the_same_folder(tmp_path):
    """HAOS users who symlinked /media/evon_recordings -> /config/media/evon_recordings."""
    config_media = tmp_path / "config" / "media"
    (config_media / "evon_recordings").mkdir(parents=True)
    (config_media / "evon_recordings" / "keep.mp4").write_bytes(b"k")
    media = tmp_path / "media"
    media.mkdir()
    (media / "evon_recordings").symlink_to(config_media / "evon_recordings", target_is_directory=True)
    hass = _hass(tmp_path / "config", {"local": str(media)})

    target = prepare_recordings_dir(hass)

    assert target == media / "evon_recordings"
    assert (config_media / "evon_recordings" / "keep.mp4").read_bytes() == b"k"


def test_prepare_without_legacy_folder(tmp_path):
    hass = _hass(tmp_path / "config", {"local": str(tmp_path / "media")})
    target = prepare_recordings_dir(hass)
    assert target.is_dir()
