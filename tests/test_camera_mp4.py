"""Tests for camera MP4 finalization (C-M1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_UTC = timezone.utc  # noqa: UP017


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
def mock_camera():
    """Create a mock EvonCamera instance."""
    camera = MagicMock()
    camera.entity_id = "camera.test_cam"
    camera.name = "Test Cam"
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    camera.async_camera_image = AsyncMock(return_value=jpeg)
    return camera


@pytest.fixture
def recorder(mock_hass, mock_camera):
    """Create an EvonCameraRecorder instance."""
    from custom_components.evon.camera_recorder import EvonCameraRecorder

    return EvonCameraRecorder(mock_hass, mock_camera)


def _create_test_jpeg() -> bytes:
    """Create a minimal valid JPEG for testing."""
    try:
        from PIL import Image

        img = Image.new("RGB", (64, 48), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


class TestFinalizeRecording:
    """Test _finalize_recording path, frame processing, and output."""

    @pytest.mark.asyncio
    async def test_finalize_no_frames_returns_none(self, recorder):
        """Test finalize with empty frames returns None and resets to IDLE."""
        from custom_components.evon.camera_recorder import RecordingState

        recorder._state = RecordingState.RECORDING
        result = await recorder._finalize_recording()

        assert result is None
        assert recorder.state == RecordingState.IDLE

    @pytest.mark.asyncio
    async def test_finalize_calls_encode_mp4(self, recorder, mock_hass, tmp_path):
        """Test finalize invokes _encode_mp4 with correct output path."""
        from custom_components.evon.camera_recorder import RecordingState

        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        now = datetime(2024, 3, 15, 10, 30, 0, tzinfo=_UTC)
        recorder._recording_start = now
        recorder._state = RecordingState.RECORDING
        recorder._frames.append((_create_test_jpeg(), now))

        encode_calls = []

        def mock_encode(mp4_path):
            encode_calls.append(str(mp4_path))

        with patch.object(recorder, "_encode_mp4", side_effect=mock_encode):
            result = await recorder._finalize_recording()

        assert result is not None
        assert "Test_Cam_20240315_103000.mp4" in result
        assert len(encode_calls) == 1
        assert "Test_Cam_20240315_103000.mp4" in encode_calls[0]
        assert recorder.state == RecordingState.IDLE

    @pytest.mark.asyncio
    async def test_finalize_saves_jpeg_frames_when_requested(self, recorder, mock_hass, tmp_path):
        """Test finalize saves JPEG frames when output format is mp4_and_frames."""
        from custom_components.evon.camera_recorder import RecordingState
        from custom_components.evon.const import RECORDING_OUTPUT_MP4_AND_FRAMES

        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        now = datetime(2024, 3, 15, 10, 30, 0, tzinfo=_UTC)
        recorder._recording_start = now
        recorder._state = RecordingState.RECORDING
        recorder._output_format = RECORDING_OUTPUT_MP4_AND_FRAMES

        jpeg = _create_test_jpeg()
        recorder._frames.append((jpeg, now))
        recorder._frames.append((jpeg, now + timedelta(seconds=1)))

        save_calls = []

        def mock_save_frames(frames_dir):
            save_calls.append(str(frames_dir))

        with (
            patch.object(recorder, "_encode_mp4"),
            patch.object(recorder, "_save_jpeg_frames", side_effect=mock_save_frames),
        ):
            await recorder._finalize_recording()

        assert len(save_calls) == 1
        assert "Test_Cam_20240315_103000" in save_calls[0]

    @pytest.mark.asyncio
    async def test_finalize_clears_frames_on_error(self, recorder, mock_hass, tmp_path):
        """Test finalize clears frames even when encoding fails."""
        from custom_components.evon.camera_recorder import RecordingState

        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        now = datetime(2024, 3, 15, 10, 30, 0, tzinfo=_UTC)
        recorder._recording_start = now
        recorder._state = RecordingState.RECORDING
        recorder._frames.append((_create_test_jpeg(), now))

        with patch.object(recorder, "_encode_mp4", side_effect=RuntimeError("encode fail")):
            result = await recorder._finalize_recording()

        assert result is None
        assert len(recorder._frames) == 0
        assert recorder.state == RecordingState.IDLE

    @pytest.mark.asyncio
    async def test_finalize_invalidates_recordings_cache(self, recorder, mock_hass, tmp_path):
        """Test finalize sets recordings cache to None."""
        from custom_components.evon.camera_recorder import RecordingState

        mock_hass.config.path = MagicMock(side_effect=lambda *args: str(tmp_path / "/".join(args)))

        recorder._recordings_cache = [{"filename": "old.mp4"}]
        recorder._recording_start = datetime(2024, 3, 15, 10, 30, 0, tzinfo=_UTC)
        recorder._state = RecordingState.RECORDING
        recorder._frames.append((_create_test_jpeg(), datetime.now(tz=_UTC)))

        with patch.object(recorder, "_encode_mp4"):
            await recorder._finalize_recording()

        assert recorder._recordings_cache is None


class TestEncodeMp4:
    """Test _encode_mp4 frame processing with mocked av/PIL."""

    def test_encode_processes_all_valid_frames(self, recorder):
        """Test that _encode_mp4 processes all valid frames via av."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=_UTC)
        jpeg = _create_test_jpeg()
        recorder._frames.append((jpeg, now))
        recorder._frames.append((jpeg, now + timedelta(seconds=1)))
        recorder._frames.append((jpeg, now + timedelta(seconds=2)))

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
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)

        had_av = "av" in sys.modules
        old_av = sys.modules.get("av")
        sys.modules["av"] = mock_av
        try:
            with (
                patch("custom_components.evon.camera_recorder._get_timestamp_font", return_value=MagicMock()),
                patch("custom_components.evon.camera_recorder._draw_timestamp"),
                patch("PIL.Image.open", return_value=mock_img),
            ):
                mp4_path = Path("/tmp/test_all_frames.mp4")
                recorder._encode_mp4(mp4_path)

                # 3 frames encoded + 1 flush call
                assert mock_stream.encode.call_count == 4
                assert mock_av.VideoFrame.from_image.call_count == 3
        finally:
            if had_av:
                sys.modules["av"] = old_av
            else:
                del sys.modules["av"]

    def test_encode_sets_correct_stream_dimensions(self, recorder):
        """Test that stream width/height match the first valid frame."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=_UTC)
        recorder._frames.append((_create_test_jpeg(), now))

        mock_container = MagicMock()
        mock_stream = MagicMock()
        mock_stream.encode = MagicMock(return_value=[])
        mock_container.add_stream = MagicMock(return_value=mock_stream)

        mock_av = MagicMock()
        mock_av.open.return_value = mock_container
        mock_av.VideoFrame.from_image = MagicMock(return_value=MagicMock())

        mock_img = MagicMock()
        mock_img.size = (1280, 720)
        mock_img.width = 1280
        mock_img.height = 720
        mock_img.convert = MagicMock(return_value=mock_img)
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)

        had_av = "av" in sys.modules
        old_av = sys.modules.get("av")
        sys.modules["av"] = mock_av
        try:
            with (
                patch("custom_components.evon.camera_recorder._get_timestamp_font", return_value=MagicMock()),
                patch("custom_components.evon.camera_recorder._draw_timestamp"),
                patch("PIL.Image.open", return_value=mock_img),
            ):
                recorder._encode_mp4(Path("/tmp/test_dims.mp4"))

                assert mock_stream.width == 1280
                assert mock_stream.height == 720
        finally:
            if had_av:
                sys.modules["av"] = old_av
            else:
                del sys.modules["av"]
