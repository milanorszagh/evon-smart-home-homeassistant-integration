"""Camera recording manager for Evon Smart Home integration.

Evon cameras are snapshot-based (no RTSP stream). This module rapidly polls
snapshots and stitches them into an MP4 video using the av (PyAV) library.
Frame rate is limited by hardware response time (~0.5-2 FPS).
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import enum
import io
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_MAX_RECORDING_DURATION,
    DOMAIN,
    RECORDING_MEDIA_DIR,
    RECORDING_OUTPUT_MP4_AND_FRAMES,
)

if TYPE_CHECKING:
    from .camera import EvonCamera

_LOGGER = logging.getLogger(__name__)

# Minimum delay between frame captures to avoid hammering the device
_MIN_FRAME_INTERVAL = 0.5  # seconds

# TTL for the recordings filesystem cache (seconds)
_RECORDINGS_CACHE_TTL = 300  # 5 minutes


class RecordingState(enum.Enum):
    """Recording state machine."""

    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


class EvonCameraRecorder:
    """Manages snapshot-based recording for an Evon camera.

    Captures frames via the camera's async_camera_image() method, stores
    them in memory, and encodes to MP4 on stop using av (PyAV).
    """

    def __init__(self, hass: HomeAssistant, camera: EvonCamera) -> None:
        """Initialize the recorder."""
        self._hass = hass
        self._camera = camera
        self._state = RecordingState.IDLE
        self._task: asyncio.Task[None] | None = None
        self._frames: list[tuple[bytes, datetime]] = []  # (jpeg_bytes, timestamp)
        self._recording_start: datetime | None = None
        self._last_recording_path: str | None = None
        self._max_duration: int = DEFAULT_MAX_RECORDING_DURATION
        self._output_format: str = "mp4"
        self._recordings_cache: list[dict[str, str]] | None = None
        self._recordings_cache_time: float = 0.0

    @property
    def state(self) -> RecordingState:
        """Return the current recording state."""
        return self._state

    @property
    def is_recording(self) -> bool:
        """Return True if currently recording."""
        return self._state == RecordingState.RECORDING

    @property
    def recording_duration(self) -> float | None:
        """Return current recording duration in seconds."""
        if self._recording_start and self._state == RecordingState.RECORDING:
            return (dt_util.now() - self._recording_start).total_seconds()
        return None

    @property
    def last_recording_path(self) -> str | None:
        """Return the path of the last completed recording."""
        return self._last_recording_path

    async def async_start(
        self,
        max_duration: int | None = None,
        output_format: str | None = None,
    ) -> None:
        """Start recording.

        Args:
            max_duration: Maximum recording duration in seconds. Uses config value if None.
            output_format: Output format ('mp4' or 'mp4_and_frames'). Uses config value if None.
        """
        if self._state != RecordingState.IDLE:
            _LOGGER.warning("Recording already in progress for %s", self._camera.entity_id)
            return

        if max_duration is not None:
            self._max_duration = max_duration

        if output_format is not None:
            self._output_format = output_format

        self._state = RecordingState.RECORDING
        self._frames = []
        self._recording_start = dt_util.now()

        _LOGGER.info(
            "Starting recording for %s (max %ds, format: %s)",
            self._camera.entity_id,
            self._max_duration,
            self._output_format,
        )

        self._task = asyncio.create_task(self._recording_loop())

    async def async_stop(self) -> str | None:
        """Stop recording and encode to MP4.

        Returns:
            Path to the recorded MP4 file, or None if recording failed.
        """
        if self._state != RecordingState.RECORDING:
            _LOGGER.debug("No recording in progress for %s", self._camera.entity_id)
            return None

        # Cancel the recording loop
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        return await self._finalize_recording()

    async def _recording_loop(self) -> None:
        """Background task that captures frames."""
        try:
            start = time.monotonic()
            while self._state == RecordingState.RECORDING:
                elapsed = time.monotonic() - start
                if elapsed >= self._max_duration:
                    _LOGGER.info(
                        "Max recording duration reached (%ds) for %s",
                        self._max_duration,
                        self._camera.entity_id,
                    )
                    break

                # Capture a frame
                frame_start = time.monotonic()
                try:
                    image = await self._camera.async_camera_image()
                    if image:
                        self._frames.append((image, dt_util.now()))
                except Exception:
                    _LOGGER.debug("Failed to capture frame", exc_info=True)

                # Ensure minimum interval between captures
                frame_elapsed = time.monotonic() - frame_start
                if frame_elapsed < _MIN_FRAME_INTERVAL:
                    await asyncio.sleep(_MIN_FRAME_INTERVAL - frame_elapsed)

        except asyncio.CancelledError:
            _LOGGER.debug("Recording loop cancelled for %s", self._camera.entity_id)
            return

        # Auto-stop when max duration reached
        if self._state == RecordingState.RECORDING:
            await self._finalize_recording()
            # Fire event for automations
            self._hass.bus.async_fire(
                f"{DOMAIN}_recording_finished",
                {
                    "entity_id": self._camera.entity_id,
                    "path": self._last_recording_path,
                    "frames": len(self._frames),
                },
            )

    async def _finalize_recording(self) -> str | None:
        """Encode captured frames to MP4 and optionally save JPEGs."""
        if not self._frames:
            _LOGGER.warning("No frames captured for %s", self._camera.entity_id)
            self._state = RecordingState.IDLE
            return None

        self._state = RecordingState.PROCESSING

        _LOGGER.info(
            "Processing %d frames for %s",
            len(self._frames),
            self._camera.entity_id,
        )

        try:
            # Build output directory
            media_dir = Path(self._hass.config.path("media")) / RECORDING_MEDIA_DIR
            timestamp_str = self._recording_start.strftime("%Y%m%d_%H%M%S") if self._recording_start else "unknown"
            camera_name = self._camera.name or "camera"
            # Sanitize camera name for filesystem
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in camera_name)

            mp4_filename = f"{safe_name}_{timestamp_str}.mp4"
            mp4_path = media_dir / mp4_filename

            # Save JPEG frames if requested
            if self._output_format == RECORDING_OUTPUT_MP4_AND_FRAMES:
                frames_dir = media_dir / f"{safe_name}_{timestamp_str}"
                await self._hass.async_add_executor_job(self._save_jpeg_frames, frames_dir)

            # Encode MP4 in executor (CPU-intensive)
            await self._hass.async_add_executor_job(self._encode_mp4, mp4_path)

            self._last_recording_path = str(mp4_path)
            _LOGGER.info("Recording saved: %s (%d frames)", mp4_path, len(self._frames))
            return str(mp4_path)

        except Exception:
            _LOGGER.error("Failed to encode recording for %s", self._camera.entity_id, exc_info=True)
            return None
        finally:
            self._frames = []
            self._state = RecordingState.IDLE
            self._recordings_cache = None

    def _save_jpeg_frames(self, frames_dir: Path) -> None:
        """Save individual JPEG frames to disk (runs in executor)."""
        frames_dir.mkdir(parents=True, exist_ok=True)
        for jpeg_bytes, ts in self._frames:
            frame_filename = ts.strftime("%Y%m%d_%H%M%S_%f")[:-3] + ".jpg"
            (frames_dir / frame_filename).write_bytes(jpeg_bytes)

    def _encode_mp4(self, mp4_path: Path) -> None:
        """Encode JPEG frames into an MP4 file using av (PyAV).

        Runs in executor thread. Burns timestamp overlay onto each frame
        using Pillow for readability.
        """
        from fractions import Fraction

        try:
            import av
            from PIL import Image
        except ImportError as err:
            _LOGGER.error("Camera recording requires PyAV and Pillow packages. Install with: pip install PyAV Pillow")
            raise HomeAssistantError(
                "Recording failed: PyAV package not installed. Try reinstalling the Evon integration."
            ) from err

        mp4_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine frame dimensions from first frame
        first_image = Image.open(io.BytesIO(self._frames[0][0]))
        width, height = first_image.size

        # Calculate actual FPS from frame timestamps
        if len(self._frames) >= 2:
            total_time = (self._frames[-1][1] - self._frames[0][1]).total_seconds()
            fps = len(self._frames) / total_time if total_time > 0 else 1.0
        else:
            fps = 1.0

        # Clamp FPS to reasonable range
        fps = max(0.5, min(fps, 10.0))

        # PyAV requires a Fraction for the rate parameter
        fps_fraction = Fraction(fps).limit_denominator(1000)

        # Load font for timestamp overlay
        font = _get_timestamp_font(height)

        container = av.open(str(mp4_path), mode="w")
        try:
            stream = container.add_stream("h264", rate=fps_fraction)
            stream.width = width
            stream.height = height
            stream.pix_fmt = "yuv420p"

            for jpeg_bytes, ts in self._frames:
                img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")

                # Burn timestamp overlay
                _draw_timestamp(img, ts, font)

                frame = av.VideoFrame.from_image(img)
                for packet in stream.encode(frame):
                    container.mux(packet)

            # Flush encoder
            for packet in stream.encode():
                container.mux(packet)
        finally:
            container.close()

    def get_recent_recordings(self, limit: int = 5) -> list[dict[str, str]]:
        """Return recent recordings for this camera.

        Scans the recordings directory for MP4 files matching this camera's
        safe name prefix, sorted by modification time (newest first).
        Results are cached for ``_RECORDINGS_CACHE_TTL`` seconds.

        Args:
            limit: Maximum number of recordings to return.

        Returns:
            List of dicts with filename, timestamp, size, and url.
        """
        now = time.monotonic()
        if self._recordings_cache is not None and now - self._recordings_cache_time < _RECORDINGS_CACHE_TTL:
            return self._recordings_cache[:limit]

        media_dir = Path(self._hass.config.path("media")) / RECORDING_MEDIA_DIR
        if not media_dir.is_dir():
            self._recordings_cache = []
            self._recordings_cache_time = now
            return []

        camera_name = self._camera.name or "camera"
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in camera_name)

        mp4_files = sorted(
            (f for f in media_dir.glob(f"{safe_name}_*.mp4") if f.is_file()),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        results: list[dict[str, str]] = []
        for f in mp4_files:
            stat = f.stat()
            mtime = dt_util.utc_from_timestamp(stat.st_mtime)
            size_bytes = stat.st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"

            results.append(
                {
                    "filename": f.name,
                    "timestamp": mtime.strftime("%-b %-d at %-I:%M %p"),
                    "size": size_str,
                    "url": f"/evon/recordings/{f.name}",
                }
            )

        self._recordings_cache = results
        self._recordings_cache_time = now
        return results[:limit]

    def get_extra_attributes(self) -> dict[str, Any]:
        """Return recording-related extra state attributes."""
        attrs: dict[str, Any] = {
            "recording": self.is_recording,
        }
        if self.is_recording and self._recording_start:
            attrs["recording_duration"] = round((dt_util.now() - self._recording_start).total_seconds(), 1)
            attrs["recording_frames"] = len(self._frames)
        if self._last_recording_path:
            attrs["last_recording_path"] = self._last_recording_path
        return attrs


def _get_timestamp_font(image_height: int) -> Any:
    """Get a font for timestamp overlay, sized relative to image height."""
    from PIL import ImageFont

    font_size = max(12, image_height // 25)
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
        except OSError:
            return ImageFont.load_default()


def _draw_timestamp(img: Any, ts: datetime, font: Any) -> None:
    """Draw timestamp overlay on an image (bottom-right, white with black outline)."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    text = ts.strftime("%Y-%m-%d %H:%M:%S")

    # Measure text size
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Position: bottom-right with padding
    padding = 8
    x = img.width - text_width - padding
    y = img.height - text_height - padding

    # Draw black outline/shadow for readability
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, fill="black", font=font)

    # Draw white text
    draw.text((x, y), text, fill="white", font=font)
