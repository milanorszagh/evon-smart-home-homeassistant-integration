"""Authenticated HTTP view for serving Evon camera recordings.

Replaces the previous unauthenticated ``/evon/recordings`` static path. Static
paths registered via ``async_register_static_paths`` are served without any auth
check (same as the ``www/`` folder), which made every camera recording MP4
downloadable by anyone who could reach the Home Assistant HTTP port — including
over a Nabu Casa remote URL or reverse proxy.

``HomeAssistantView`` enforces auth by default (``requires_auth = True``), so
both a bearer token and an ``auth/sign_path`` signed URL — the latter is what
the Lovelace card uses for inline ``<video>`` playback — are accepted, while an
anonymous request gets 401. Files also remain browsable through ``media_source``
(the HA media browser), which is likewise auth-gated.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)


class EvonRecordingsView(HomeAssistantView):
    """Serve Evon camera recording files behind Home Assistant auth."""

    url = "/evon/recordings/{filename}"
    name = "evon:recordings"
    requires_auth = True

    def __init__(self, recordings_dir: str) -> None:
        """Store the directory that holds the recording files."""
        self._recordings_dir = Path(recordings_dir).resolve()

    async def get(self, request: web.Request, filename: str) -> web.StreamResponse:
        """Serve a single recording file, rejecting path traversal.

        The ``{filename}`` route segment cannot itself contain a ``/``, but we
        still reject separators / dot segments and confirm the resolved path
        stays inside the recordings directory before serving.
        """
        if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
            raise web.HTTPNotFound

        candidate = (self._recordings_dir / filename).resolve()
        if not candidate.is_relative_to(self._recordings_dir) or not candidate.is_file():
            raise web.HTTPNotFound

        return web.FileResponse(candidate)
