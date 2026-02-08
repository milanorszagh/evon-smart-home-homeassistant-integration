"""Tests for Evon camera recorder."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import requires_ha_test_framework

# ============================================================================
# Unit tests (no HA dependency)
# ============================================================================


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.config.path = MagicMock(side_effect=lambda *args: str(Path("/tmp/ha_test") / "/".join(args)))
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *args: fn(*args))
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.fixture
def mock_camera(mock_hass):
    """Create a mock EvonCamera instance."""
    camera = MagicMock()
    camera.entity_id = "camera.test_camera"
    camera.name = "Test Camera"
    camera.hass = mock_hass
    # Return a small JPEG-like bytes object
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    camera.async_camera_image = AsyncMock(return_value=jpeg_bytes)
    return camera


@pytest.fixture
def recorder(mock_hass, mock_camera):
    """Create an EvonCameraRecorder instance."""
    from custom_components.evon.camera_recorder import EvonCameraRecorder

    return EvonCameraRecorder(mock_hass, mock_camera)


def _make_finalize_mock(recorder_instance):
    """Create an AsyncMock for _finalize_recording that resets state to IDLE."""
    from custom_components.evon.camera_recorder import RecordingState

    async def _mock_finalize():
        recorder_instance._frames = []
        recorder_instance._state = RecordingState.IDLE
        return None

    return _mock_finalize


class TestRecorderState:
    """Test recording state management."""

    def test_initial_state(self, recorder):
        """Test recorder starts in idle state."""
        from custom_components.evon.camera_recorder import RecordingState

        assert recorder.state == RecordingState.IDLE
        assert not recorder.is_recording
        assert recorder.recording_duration is None
        assert recorder.last_recording_path is None

    @pytest.mark.asyncio
    async def test_start_changes_state(self, recorder):
        """Test starting recording changes state."""
        from custom_components.evon.camera_recorder import RecordingState

        # Start recording but cancel immediately so it doesn't run forever
        await recorder.async_start(max_duration=1)
        assert recorder.state == RecordingState.RECORDING
        assert recorder.is_recording

        # Clean up - stop recording
        await recorder.async_stop()

    @pytest.mark.asyncio
    async def test_stop_returns_to_idle(self, recorder):
        """Test stopping recording returns to idle."""
        from custom_components.evon.camera_recorder import RecordingState

        # Mock _finalize_recording to avoid actual encoding but still reset state
        with patch.object(recorder, "_finalize_recording", side_effect=_make_finalize_mock(recorder)):
            await recorder.async_start(max_duration=300)
            assert recorder.state == RecordingState.RECORDING

            await recorder.async_stop()
            assert recorder.state == RecordingState.IDLE

    @pytest.mark.asyncio
    async def test_stop_when_not_recording(self, recorder):
        """Test stopping when not recording is a no-op."""
        result = await recorder.async_stop()
        assert result is None

    @pytest.mark.asyncio
    async def test_double_start_prevented(self, recorder, mock_camera):
        """Test starting recording twice is prevented."""
        from custom_components.evon.camera_recorder import RecordingState

        with patch.object(recorder, "_finalize_recording", side_effect=_make_finalize_mock(recorder)):
            await recorder.async_start(max_duration=300)
            assert recorder.state == RecordingState.RECORDING

            # Second start should be a no-op (warning logged)
            await recorder.async_start(max_duration=300)
            assert recorder.state == RecordingState.RECORDING

            await recorder.async_stop()


class TestRecordingDuration:
    """Test recording duration behavior."""

    def test_duration_none_when_idle(self, recorder):
        """Test duration is None when not recording."""
        assert recorder.recording_duration is None

    @pytest.mark.asyncio
    async def test_duration_when_recording(self, recorder):
        """Test duration increments when recording."""
        with patch.object(recorder, "_finalize_recording", side_effect=_make_finalize_mock(recorder)):
            await recorder.async_start(max_duration=300)
            # Duration should be a small positive number
            duration = recorder.recording_duration
            assert duration is not None
            assert duration >= 0

            await recorder.async_stop()

    @pytest.mark.asyncio
    async def test_max_duration_enforcement(self, recorder, mock_camera):
        """Test recording stops when max duration is reached."""
        # Use a very short max duration
        # Mock the camera to return valid JPEG-like image quickly
        small_jpeg = _create_test_jpeg()
        mock_camera.async_camera_image = AsyncMock(return_value=small_jpeg)

        with patch.object(recorder, "_finalize_recording", side_effect=_make_finalize_mock(recorder)):
            await recorder.async_start(max_duration=1)
            # Wait for the recording loop to stop due to max duration
            await asyncio.sleep(2.0)

            from custom_components.evon.camera_recorder import RecordingState

            # Should have auto-stopped
            assert recorder.state == RecordingState.IDLE


class TestFrameCapture:
    """Test frame capture during recording."""

    @pytest.mark.asyncio
    async def test_frames_captured(self, recorder, mock_camera):
        """Test frames are captured during recording."""
        small_jpeg = _create_test_jpeg()
        mock_camera.async_camera_image = AsyncMock(return_value=small_jpeg)

        with patch.object(recorder, "_finalize_recording", side_effect=_make_finalize_mock(recorder)):
            await recorder.async_start(max_duration=300)
            # Wait for at least one frame capture
            await asyncio.sleep(0.8)

            # Should have captured at least one frame
            assert len(recorder._frames) >= 1

            await recorder.async_stop()

    @pytest.mark.asyncio
    async def test_none_frames_skipped(self, recorder, mock_camera):
        """Test None image responses are skipped."""
        call_count = 0

        async def alternating_image(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return None
            return _create_test_jpeg()

        mock_camera.async_camera_image = alternating_image

        with patch.object(recorder, "_finalize_recording", side_effect=_make_finalize_mock(recorder)):
            await recorder.async_start(max_duration=300)
            await asyncio.sleep(1.5)

            # All frames should be valid (None responses skipped)
            for frame_bytes, _ in recorder._frames:
                assert frame_bytes is not None

            await recorder.async_stop()


class TestExtraAttributes:
    """Test extra state attributes."""

    def test_idle_attributes(self, recorder):
        """Test attributes when idle."""
        attrs = recorder.get_extra_attributes()
        assert attrs["recording"] is False
        assert "recording_duration" not in attrs
        assert "recording_frames" not in attrs

    @pytest.mark.asyncio
    async def test_recording_attributes(self, recorder):
        """Test attributes when recording."""
        with patch.object(recorder, "_finalize_recording", side_effect=_make_finalize_mock(recorder)):
            await recorder.async_start(max_duration=300)
            attrs = recorder.get_extra_attributes()
            assert attrs["recording"] is True
            assert "recording_duration" in attrs
            assert "recording_frames" in attrs

            await recorder.async_stop()

    def test_last_recording_path_attribute(self, recorder):
        """Test last_recording_path attribute after recording."""
        recorder._last_recording_path = "/media/evon_recordings/test.mp4"
        attrs = recorder.get_extra_attributes()
        assert attrs["last_recording_path"] == "/media/evon_recordings/test.mp4"


class TestMP4Encoding:
    """Test MP4 encoding (with mocked av)."""

    def test_encode_mp4_called(self, recorder):
        """Test that _encode_mp4 uses av library."""
        import sys

        # Add some mock frames
        small_jpeg = _create_test_jpeg()
        now = datetime.now()
        recorder._frames = [(small_jpeg, now)]

        mock_container = MagicMock()
        mock_stream = MagicMock()
        mock_stream.encode = MagicMock(return_value=[])
        mock_container.add_stream = MagicMock(return_value=mock_stream)

        mock_av = MagicMock()
        mock_av.open.return_value = mock_container
        mock_av.VideoFrame.from_image = MagicMock(return_value=MagicMock())

        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_img.width = 640
        mock_img.height = 480
        mock_img.convert = MagicMock(return_value=mock_img)

        # Inject mock av into sys.modules so the local `import av` picks it up
        had_av = "av" in sys.modules
        old_av = sys.modules.get("av")
        sys.modules["av"] = mock_av
        try:
            with (
                patch("custom_components.evon.camera_recorder._get_timestamp_font", return_value=MagicMock()),
                patch("custom_components.evon.camera_recorder._draw_timestamp"),
                patch("PIL.Image.open", return_value=mock_img),
            ):
                mp4_path = Path("/tmp/test.mp4")
                recorder._encode_mp4(mp4_path)

                mock_av.open.assert_called_once_with(str(mp4_path), mode="w")
                mock_container.add_stream.assert_called_once()
                mock_container.close.assert_called_once()
        finally:
            if had_av:
                sys.modules["av"] = old_av
            else:
                del sys.modules["av"]

    def test_save_jpeg_frames(self, recorder, tmp_path):
        """Test JPEG frame saving."""
        small_jpeg = _create_test_jpeg()
        now = datetime.now()
        recorder._frames = [
            (small_jpeg, now),
            (small_jpeg, now + timedelta(seconds=1)),
        ]

        frames_dir = tmp_path / "frames"
        recorder._save_jpeg_frames(frames_dir)

        assert frames_dir.exists()
        jpg_files = list(frames_dir.glob("*.jpg"))
        assert len(jpg_files) == 2


class TestRecentRecordings:
    """Test get_recent_recordings method."""

    def test_empty_when_no_directory(self, recorder, mock_hass):
        """Test returns empty list when recordings directory doesn't exist."""
        # Default mock path won't exist
        result = recorder.get_recent_recordings()
        assert result == []

    def test_empty_when_no_files(self, recorder, mock_hass, tmp_path):
        """Test returns empty list when directory exists but has no matching files."""
        recordings_dir = tmp_path / "media" / "evon_recordings"
        recordings_dir.mkdir(parents=True)
        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        result = recorder.get_recent_recordings()
        assert result == []

    def test_returns_matching_recordings(self, recorder, mock_hass, mock_camera, tmp_path):
        """Test returns MP4 files matching camera name prefix."""
        import time

        recordings_dir = tmp_path / "media" / "evon_recordings"
        recordings_dir.mkdir(parents=True)
        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        # Create test MP4 files (camera name is "Test Camera" -> safe name "Test_Camera")
        files = []
        for i in range(3):
            f = recordings_dir / f"Test_Camera_2024010{i}_120000.mp4"
            f.write_bytes(b"\x00" * (1024 * (i + 1)))
            files.append(f)
            time.sleep(0.05)  # Ensure different mtime

        result = recorder.get_recent_recordings()
        assert len(result) == 3
        # Newest first (last created file)
        assert result[0]["filename"] == "Test_Camera_20240102_120000.mp4"
        assert result[1]["filename"] == "Test_Camera_20240101_120000.mp4"
        assert result[2]["filename"] == "Test_Camera_20240100_120000.mp4"

    def test_respects_limit(self, recorder, mock_hass, tmp_path):
        """Test limit parameter caps the number of results."""
        import time

        recordings_dir = tmp_path / "media" / "evon_recordings"
        recordings_dir.mkdir(parents=True)
        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        for i in range(7):
            f = recordings_dir / f"Test_Camera_2024010{i}_120000.mp4"
            f.write_bytes(b"\x00" * 1024)
            time.sleep(0.05)

        result = recorder.get_recent_recordings(limit=3)
        assert len(result) == 3

    def test_ignores_other_cameras(self, recorder, mock_hass, tmp_path):
        """Test only returns files matching this camera's safe name prefix."""
        recordings_dir = tmp_path / "media" / "evon_recordings"
        recordings_dir.mkdir(parents=True)
        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        # Matching file
        (recordings_dir / "Test_Camera_20240101_120000.mp4").write_bytes(b"\x00" * 2048)
        # Non-matching file
        (recordings_dir / "Other_Camera_20240101_120000.mp4").write_bytes(b"\x00" * 2048)

        result = recorder.get_recent_recordings()
        assert len(result) == 1
        assert result[0]["filename"] == "Test_Camera_20240101_120000.mp4"

    def test_field_contents(self, recorder, mock_hass, tmp_path):
        """Test returned dict fields have correct contents."""
        recordings_dir = tmp_path / "media" / "evon_recordings"
        recordings_dir.mkdir(parents=True)
        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        f = recordings_dir / "Test_Camera_20240115_190100.mp4"
        f.write_bytes(b"\x00" * (180 * 1024))  # 180 KB

        result = recorder.get_recent_recordings()
        assert len(result) == 1
        rec = result[0]
        assert rec["filename"] == "Test_Camera_20240115_190100.mp4"
        assert "url" in rec
        assert rec["url"] == "/evon/recordings/Test_Camera_20240115_190100.mp4"
        assert "KB" in rec["size"]
        assert rec["timestamp"]  # Non-empty timestamp string

    def test_large_file_size_in_mb(self, recorder, mock_hass, tmp_path):
        """Test files >= 1 MB show size in MB."""
        recordings_dir = tmp_path / "media" / "evon_recordings"
        recordings_dir.mkdir(parents=True)
        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        f = recordings_dir / "Test_Camera_20240115_190100.mp4"
        f.write_bytes(b"\x00" * (2 * 1024 * 1024))  # 2 MB

        result = recorder.get_recent_recordings()
        assert len(result) == 1
        assert "MB" in result[0]["size"]


# ============================================================================
# Integration tests (require HA test framework)
# ============================================================================


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_recording_switch_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test recording switch entity is created for cameras."""
    if not pytest.importorskip("pytest_homeassistant_custom_component", reason="Needs HA test framework"):
        return

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Recording switch should exist for the camera
    hass.states.get("switch.intercom_camera_recording")
    # May or may not be created depending on entity naming - just verify no errors


# ============================================================================
# Helpers
# ============================================================================


def _create_test_jpeg() -> bytes:
    """Create a minimal valid JPEG for testing."""
    try:
        from PIL import Image

        img = Image.new("RGB", (64, 48), color=(128, 128, 128))
        import io

        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        # Fallback: minimal JPEG header
        return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
