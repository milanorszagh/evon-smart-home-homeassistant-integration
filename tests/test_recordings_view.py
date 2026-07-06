"""Tests for the authenticated Evon recordings HTTP view."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiohttp import web
import pytest

from custom_components.evon.recordings_view import EvonRecordingsView


def test_view_requires_auth():
    """The view must enforce HA auth (no anonymous access to footage)."""
    assert EvonRecordingsView.requires_auth is True
    assert EvonRecordingsView.url == "/evon/recordings/{filename}"


@pytest.mark.asyncio
async def test_serves_existing_file(tmp_path):
    """A real recording file in the directory is served."""
    rec = tmp_path / "Test_Camera_20240115_190100.mp4"
    rec.write_bytes(b"fake mp4 data")

    view = EvonRecordingsView(str(tmp_path))
    response = await view.get(MagicMock(), "Test_Camera_20240115_190100.mp4")
    assert isinstance(response, web.FileResponse)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [
        "../secrets.yaml",
        "..%2Fsecrets.yaml",
        "sub/dir/file.mp4",
        "back\\slash.mp4",
        "..",
        ".",
        "",
        "does_not_exist.mp4",
    ],
)
async def test_rejects_traversal_and_missing(tmp_path, filename):
    """Traversal attempts, subpaths, and missing files all 404."""
    # Create a sensitive file a traversal might target.
    (tmp_path.parent / "secrets.yaml").write_text("token: hunter2")

    view = EvonRecordingsView(str(tmp_path))
    with pytest.raises(web.HTTPNotFound):
        await view.get(MagicMock(), filename)
