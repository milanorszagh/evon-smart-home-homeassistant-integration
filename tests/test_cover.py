"""Integration tests for Evon cover (blind) platform."""

from __future__ import annotations

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
