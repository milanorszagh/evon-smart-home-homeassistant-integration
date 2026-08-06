"""Integration tests for Evon cover (blind) platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_cover_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test cover platform setup creates entities."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Check that cover entity was created
    state = hass.states.get("cover.living_room_blind")
    assert state is not None
    # Evon position 50 -> HA position 50 (100 - 50 = 50)
    # Evon angle 45 -> HA tilt 55 (100 - 45 = 55)
    assert state.attributes.get("current_position") == 50
    assert state.attributes.get("current_tilt_position") == 55


@pytest.mark.asyncio
async def test_cover_open(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test opening a cover."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    mock_evon_api_class.open_blind.assert_called_once_with("blind_1")


@pytest.mark.asyncio
async def test_cover_close(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test closing a cover."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    mock_evon_api_class.close_blind.assert_called_once_with("blind_1")


@pytest.mark.asyncio
async def test_cover_stop(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test stopping a cover."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    mock_evon_api_class.stop_blind.assert_called_once_with("blind_1")


@pytest.mark.asyncio
async def test_cover_set_position(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting cover position."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Set position to 75% open (HA) = 25% closed (Evon)
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.living_room_blind", "position": 75},
        blocking=True,
    )

    # HA position 75 = Evon position 25 (inverted)
    mock_evon_api_class.set_blind_position.assert_called_once_with("blind_1", 25)


@pytest.mark.asyncio
async def test_cover_set_tilt(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting cover tilt position."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Set HA tilt to 60% open -> Evon angle 40 (100 - 60 = 40)
    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.living_room_blind", "tilt_position": 60},
        blocking=True,
    )

    # HA tilt 60 = Evon angle 40 (inverted)
    mock_evon_api_class.set_blind_tilt.assert_called_once_with("blind_1", 40)


@pytest.mark.asyncio
async def test_cover_optimistic_position(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that optimistic position updates are applied immediately."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial position
    state = hass.states.get("cover.living_room_blind")
    assert state.attributes.get("current_position") == 50

    # Set new position - optimistic update
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.living_room_blind", "position": 100},
        blocking=True,
    )

    # State should reflect the optimistic update
    state = hass.states.get("cover.living_room_blind")
    assert state.attributes.get("current_position") == 100


@pytest.mark.asyncio
async def test_cover_open_tilt(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test opening cover tilt (slats horizontal)."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    # HA open tilt (100) = Evon angle 0 (horizontal/open)
    mock_evon_api_class.set_blind_tilt.assert_called_once_with("blind_1", 0)


@pytest.mark.asyncio
async def test_cover_close_tilt(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test closing cover tilt (slats blocking)."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    # HA close tilt (0) = Evon angle 100 (closed/blocking)
    mock_evon_api_class.set_blind_tilt.assert_called_once_with("blind_1", 100)


@pytest.mark.asyncio
async def test_cover_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test cover entity attributes."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.living_room_blind")
    assert state is not None

    # Check evon_id attribute
    assert state.attributes.get("evon_id") == "blind_1"

    # Check device class
    assert state.attributes.get("device_class") == "blind"

    # Check evon_angle attribute (raw Evon value)
    assert state.attributes.get("evon_angle") == 45


@pytest.mark.asyncio
async def test_cover_group_open(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test opening a blind group calls open_all_blinds instead of open_blind."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Verify group entity exists
    state = hass.states.get("cover.all_living_room_blinds")
    assert state is not None

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.all_living_room_blinds"},
        blocking=True,
    )

    mock_evon_api_class.open_all_blinds.assert_called_once()
    mock_evon_api_class.open_blind.assert_not_called()


@pytest.mark.asyncio
async def test_cover_group_close(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test closing a blind group calls close_all_blinds instead of close_blind."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.all_living_room_blinds")
    assert state is not None

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.all_living_room_blinds"},
        blocking=True,
    )

    mock_evon_api_class.close_all_blinds.assert_called_once()
    mock_evon_api_class.close_blind.assert_not_called()


@pytest.mark.asyncio
async def test_cover_group_stop(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test stopping a blind group calls stop_all_blinds instead of stop_blind."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.all_living_room_blinds")
    assert state is not None

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.all_living_room_blinds"},
        blocking=True,
    )

    mock_evon_api_class.stop_all_blinds.assert_called_once()
    mock_evon_api_class.stop_blind.assert_not_called()


@pytest.mark.asyncio
async def test_cover_is_closed(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test is_closed returns True when position is 0 (Evon position 100 = fully closed)."""
    from tests.conftest import MOCK_INSTANCE_DETAILS

    original_position = MOCK_INSTANCE_DETAILS["blind_1"]["Position"]
    try:
        # Evon Position 100 = fully closed -> HA position 0 = closed
        MOCK_INSTANCE_DETAILS["blind_1"]["Position"] = 100

        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("cover.living_room_blind")
        assert state is not None
        assert state.attributes.get("current_position") == 0
        assert state.state == "closed"
    finally:
        MOCK_INSTANCE_DETAILS["blind_1"]["Position"] = original_position


@pytest.mark.asyncio
async def test_cover_open_while_moving_stops(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that calling open_cover when the blind is already moving acts as stop toggle."""
    from tests.conftest import MOCK_INSTANCE_DETAILS

    original_is_moving = MOCK_INSTANCE_DETAILS["blind_1"]["IsMoving"]
    try:
        # Set blind as currently moving
        MOCK_INSTANCE_DETAILS["blind_1"]["IsMoving"] = True

        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": "cover.living_room_blind"},
            blocking=True,
        )

        # The API should still be called (toggle behavior is on the hardware side)
        mock_evon_api_class.open_blind.assert_called_once_with("blind_1")

        # But optimistic state should show the blind as no longer moving
        state = hass.states.get("cover.living_room_blind")
        assert state is not None
        # When moving blind is toggled, it stops - state should not be "opening"
        assert state.state != "opening"
    finally:
        MOCK_INSTANCE_DETAILS["blind_1"]["IsMoving"] = original_is_moving


@pytest.mark.asyncio
async def test_cover_api_error_resets_optimistic_state(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that when set_blind_position raises EvonApiError, the optimistic state is cleared."""
    from custom_components.evon.api import EvonApiError

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial state
    state = hass.states.get("cover.living_room_blind")
    assert state is not None
    original_position = state.attributes.get("current_position")

    # Make set_blind_position raise EvonApiError
    mock_evon_api_class.set_blind_position.side_effect = EvonApiError("Connection failed")

    with pytest.raises(EvonApiError):
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": "cover.living_room_blind", "position": 100},
            blocking=True,
        )

    # State should revert to original (optimistic state was cleared on error)
    state = hass.states.get("cover.living_room_blind")
    assert state.attributes.get("current_position") == original_position


@pytest.mark.asyncio
async def test_cover_optimistic_tilt(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test optimistic tilt update is applied immediately after set_cover_tilt_position."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial tilt: Evon angle 45 -> HA tilt 55
    state = hass.states.get("cover.living_room_blind")
    assert state.attributes.get("current_tilt_position") == 55

    # Set tilt to 80 - optimistic update should apply immediately
    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.living_room_blind", "tilt_position": 80},
        blocking=True,
    )

    # State should reflect the optimistic tilt update
    state = hass.states.get("cover.living_room_blind")
    assert state.attributes.get("current_tilt_position") == 80


@pytest.mark.asyncio
async def test_cover_is_opening_is_closing(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test is_opening returns True after open_cover, is_closing after close_cover on stopped blind."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial state: blind is stopped (IsMoving=False)
    state = hass.states.get("cover.living_room_blind")
    assert state is not None
    assert state.state != "opening"
    assert state.state != "closing"

    # Open the cover - optimistic state should show "opening"
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    state = hass.states.get("cover.living_room_blind")
    assert state.state == "opening"

    # Reset mock and state by re-setting up
    # Stop the cover first to reset optimistic state
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    # Close the cover - optimistic state should show "closing"
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    state = hass.states.get("cover.living_room_blind")
    assert state.state == "closing"


# =============================================================================
# Post-Command Recheck Tests (EvonCover)
# =============================================================================


class TestCoverPostCommandRecheck:
    """Test that EvonCover commands schedule a deferred recheck instead of immediate refresh."""

    @pytest.fixture
    def cover_entity(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Create an EvonCover with a wired-up mock coordinator."""
        from unittest.mock import MagicMock

        from custom_components.evon.cover import EvonCover

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = {
            "blinds": [{"id": "blind_1", "name": "Test Blind", "position": 50, "angle": 45, "is_moving": False}]
        }
        coordinator.get_entity_data = MagicMock(
            return_value={"id": "blind_1", "name": "Test Blind", "position": 50, "angle": 45, "is_moving": False}
        )

        entry = mock_config_entry_v2
        api = mock_evon_api_class

        cover = EvonCover(coordinator, "blind_1", "Test Blind", "Living Room", entry, api)
        cover.hass = hass
        cover.entity_id = "cover.test_blind"
        # Bypass state writing: entity is not registered in the state machine
        cover.async_write_ha_state = MagicMock()
        return cover

    @pytest.mark.asyncio
    async def test_open_schedules_recheck(self, cover_entity, mock_evon_api_class):
        """open_cover schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        cover = cover_entity
        cover.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await cover.async_open_cover()

        # No immediate refresh
        cover.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_close_schedules_recheck(self, cover_entity, mock_evon_api_class):
        """close_cover schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        cover = cover_entity
        cover.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await cover.async_close_cover()

        # No immediate refresh
        cover.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_set_position_schedules_recheck(self, cover_entity, mock_evon_api_class):
        """set_cover_position schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        cover = cover_entity
        cover.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await cover.async_set_cover_position(position=75)

        # No immediate refresh
        cover.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_set_tilt_schedules_recheck(self, cover_entity, mock_evon_api_class):
        """set_cover_tilt_position schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        cover = cover_entity
        cover.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await cover.async_set_cover_tilt_position(tilt_position=60)

        # No immediate refresh
        cover.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_stop_schedules_recheck(self, cover_entity, mock_evon_api_class):
        """RV-D3: async_stop_cover schedules a recheck so the resting position is
        fetched within the quiesce window (up to 60s otherwise in HTTP-only mode)."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        cover = cover_entity
        cover.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await cover.async_stop_cover()

        cover.coordinator.async_request_refresh.assert_not_called()
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    @pytest.mark.parametrize("command", ["open", "close"])
    async def test_toggle_stop_schedules_recheck(self, cover_entity, mock_evon_api_class, command):
        """RV-D3: open/close while already moving acts as a stop toggle and must also
        schedule a recheck to fetch the resting position."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        cover = cover_entity
        cover.coordinator.async_request_refresh = AsyncMock()
        # Blind is currently moving -> the command becomes a stop toggle.
        cover.coordinator.get_entity_data = MagicMock(
            return_value={"id": "blind_1", "name": "Test Blind", "position": 50, "angle": 45, "is_moving": True}
        )

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            if command == "open":
                await cover.async_open_cover()
            else:
                await cover.async_close_cover()

        cover.coordinator.async_request_refresh.assert_not_called()
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD


# =============================================================================
# Cover-specific quiesce + lifecycle regression guards
# =============================================================================


class TestCoverQuiesceBehavior:
    """Pin cover-specific quiesce invariants:
    - API position/angle caches must update even when async_write_ha_state is suppressed
      (the API caches feed WS control's MoveToPosition calls, which would break if stale).
    - async_stop_cover must reset _optimistic_state_set_at so subsequent updates aren't
      dropped by a stale quiesce window (Fix #3).
    """

    def _make_cover(self, hass, mock_config_entry_v2, mock_evon_api_class):
        from unittest.mock import MagicMock

        from custom_components.evon.cover import EvonCover

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.get_entity_data = MagicMock(
            return_value={
                "id": "blind_1",
                "name": "Test Blind",
                "position": 50,
                "angle": 45,
                "is_moving": False,
            }
        )
        cover = EvonCover(
            coordinator, "blind_1", "Test Blind", "Living Room", mock_config_entry_v2, mock_evon_api_class
        )
        cover.hass = hass
        cover.async_write_ha_state = MagicMock()
        return cover

    def test_api_caches_update_even_during_quiesce(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Cover's API position/angle caches must update on every coordinator event
        even when the quiesce window is active (otherwise WS-based MoveToPosition
        calls would issue with stale cached values)."""
        import time
        from unittest.mock import MagicMock

        cover = self._make_cover(hass, mock_config_entry_v2, mock_evon_api_class)
        # Replace the lambda cache-updaters with MagicMocks for assertion.
        cover._api.update_blind_position = MagicMock()
        cover._api.update_blind_angle = MagicMock()

        cover._optimistic_position = 100  # User asked to fully open
        cover._optimistic_state_set_at = time.monotonic()

        # WS event mid-movement: position 30 (still moving), angle 45.
        cover.coordinator.get_entity_data.return_value = {
            "id": "blind_1",
            "name": "Test Blind",
            "position": 30,
            "angle": 45,
            "is_moving": True,
        }

        cover._handle_coordinator_update()

        # API caches WERE updated despite being in the quiesce window.
        cover._api.update_blind_position.assert_called_once_with("blind_1", 30)
        cover._api.update_blind_angle.assert_called_once_with("blind_1", 45)
        # Optimistic preserved (intermediate value doesn't match target).
        assert cover._optimistic_position == 100
        # async_write_ha_state suppressed (quiesce window active).
        cover.async_write_ha_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_resets_optimistic_timestamp(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """async_stop_cover must clear _optimistic_state_set_at so a stale quiesce
        window doesn't drop subsequent coordinator updates (Fix #3)."""
        import time

        cover = self._make_cover(hass, mock_config_entry_v2, mock_evon_api_class)
        # Simulate that a position command was just sent.
        cover._optimistic_position = 100
        cover._optimistic_state_set_at = time.monotonic()

        # Patch the recheck scheduler (RV-D3) so no real timer lingers.
        with patch("custom_components.evon.base_entity.async_call_later", return_value=MagicMock()):
            await cover.async_stop_cover()

        # Position/tilt optimistic flags cleared, AND timestamp reset.
        assert cover._optimistic_position is None
        assert cover._optimistic_tilt is None
        assert cover._optimistic_state_set_at is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("command", ["open", "close"])
    async def test_toggle_stop_resets_optimistic_timestamp(
        self, hass, mock_config_entry_v2, mock_evon_api_class, command
    ):
        """open/close while already moving acts as a stop toggle and must reset
        _optimistic_state_set_at, same as async_stop_cover (Fix #3). Otherwise a
        stale timestamp keeps quiesce suppressing updates for state that no longer
        exists, and a wall-switch move stopped this way gets is_moving=False with
        no timestamp for the 30s backstop to clear."""
        import time

        cover = self._make_cover(hass, mock_config_entry_v2, mock_evon_api_class)
        # Blind is currently moving (as if started by a wall switch).
        cover.coordinator.get_entity_data.return_value = {
            "id": "blind_1",
            "name": "Test Blind",
            "position": 50,
            "angle": 45,
            "is_moving": True,
        }
        # A recent move command left a timestamp behind.
        cover._optimistic_state_set_at = time.monotonic()

        # Patch the recheck scheduler (RV-D3) so no real timer lingers.
        with patch("custom_components.evon.base_entity.async_call_later", return_value=MagicMock()):
            if command == "open":
                await cover.async_open_cover()
            else:
                await cover.async_close_cover()

        # Toggle-stop path: is_moving optimistically False, timestamp reset.
        assert cover._optimistic_is_moving is False
        assert cover._optimistic_position is None
        assert cover._optimistic_tilt is None
        assert cover._optimistic_state_set_at is None

    @pytest.mark.asyncio
    async def test_remove_cancels_pending_recheck(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Pin lifecycle: removing the cover cancels its pending recheck timer."""
        from unittest.mock import MagicMock

        cover = self._make_cover(hass, mock_config_entry_v2, mock_evon_api_class)

        cancel_handle = MagicMock()
        with patch("custom_components.evon.base_entity.async_call_later", return_value=cancel_handle):
            cover._schedule_post_command_recheck()

        await cover.async_will_remove_from_hass()

        cancel_handle.assert_called_once()
        assert cover._recheck_cancel is None
