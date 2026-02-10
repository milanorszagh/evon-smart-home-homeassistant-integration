"""Tests for Evon button platform (scenes and identify)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.evon.api import EvonApiError
from custom_components.evon.const import LIGHT_IDENTIFY_ANIMATION_DELAY
from tests.conftest import HAS_HA_TEST_FRAMEWORK, requires_ha_test_framework

# Entity classes require proper HA base classes (metaclass inheritance)
if HAS_HA_TEST_FRAMEWORK:
    from custom_components.evon.button import EvonIdentifyButton, EvonSceneButton


# =============================================================================
# Unit tests (require HA test framework for entity class imports)
# =============================================================================


def _make_coordinator(**overrides):
    """Create a minimal mock coordinator."""
    coord = MagicMock()
    coord.last_update_success = True
    coord.data = {}
    coord.async_request_refresh = AsyncMock()
    coord.get_entity_data = MagicMock(return_value=None)
    for k, v in overrides.items():
        setattr(coord, k, v)
    return coord


def _make_api():
    """Create a mock API with light and scene methods."""
    api = AsyncMock()
    api.turn_on_light = AsyncMock()
    api.turn_off_light = AsyncMock()
    api.set_light_brightness = AsyncMock()
    api.execute_scene = AsyncMock()
    return api


def _make_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry


@requires_ha_test_framework
class TestEvonSceneButton:
    """Test EvonSceneButton entity."""

    def test_unique_id(self):
        btn = EvonSceneButton(_make_coordinator(), "System.Scene1", "Movie Night", _make_entry(), _make_api())
        assert btn._attr_unique_id == "evon_scene_System.Scene1"

    def test_name_is_none_uses_device_name(self):
        btn = EvonSceneButton(_make_coordinator(), "System.Scene1", "Movie Night", _make_entry(), _make_api())
        assert btn._attr_name is None

    def test_device_info(self):
        btn = EvonSceneButton(_make_coordinator(), "System.Scene1", "Movie Night", _make_entry(), _make_api())
        info = btn.device_info
        assert info is not None

    @pytest.mark.asyncio
    async def test_press_executes_scene(self):
        api = _make_api()
        coord = _make_coordinator()
        btn = EvonSceneButton(coord, "System.Scene1", "Movie Night", _make_entry(), api)
        await btn.async_press()
        api.execute_scene.assert_awaited_once_with("System.Scene1")
        coord.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_press_api_error_raises_ha_error(self):
        api = _make_api()
        api.execute_scene.side_effect = EvonApiError("fail")
        btn = EvonSceneButton(_make_coordinator(), "System.Scene1", "Movie Night", _make_entry(), api)
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError, match="Failed to execute scene"):
            await btn.async_press()


@requires_ha_test_framework
class TestEvonIdentifyButton:
    """Test EvonIdentifyButton entity."""

    def test_unique_id(self):
        btn = EvonIdentifyButton(
            _make_coordinator(), "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), _make_api()
        )
        assert btn._attr_unique_id == "evon_identify_SC1_M01.Light1"

    @pytest.mark.asyncio
    async def test_press_light_was_off_restores_off(self):
        """When light is off, identify should restore to off."""
        coord = _make_coordinator()
        coord.get_entity_data = MagicMock(return_value={"is_on": False, "brightness": 0})
        api = _make_api()
        btn = EvonIdentifyButton(coord, "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api)

        with patch("custom_components.evon.button.asyncio.sleep", new_callable=AsyncMock):
            await btn.async_press()

        # off -> on -> off (restore): 2 turn_off calls
        assert api.turn_off_light.await_count == 2
        api.turn_on_light.assert_awaited_once_with("SC1_M01.Light1")

    @pytest.mark.asyncio
    async def test_press_light_was_on_full_brightness_no_extra_restore(self):
        """When light was on at 100%, no brightness restore needed."""
        coord = _make_coordinator()
        coord.get_entity_data = MagicMock(return_value={"is_on": True, "brightness": 100})
        api = _make_api()
        btn = EvonIdentifyButton(coord, "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api)

        with patch("custom_components.evon.button.asyncio.sleep", new_callable=AsyncMock):
            await btn.async_press()

        api.turn_off_light.assert_awaited_once_with("SC1_M01.Light1")
        api.turn_on_light.assert_awaited_once_with("SC1_M01.Light1")
        api.set_light_brightness.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_press_light_was_on_partial_brightness_restores(self):
        """When light was on at partial brightness, restore brightness."""
        coord = _make_coordinator()
        coord.get_entity_data = MagicMock(return_value={"is_on": True, "brightness": 60})
        api = _make_api()
        btn = EvonIdentifyButton(coord, "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api)

        with patch("custom_components.evon.button.asyncio.sleep", new_callable=AsyncMock):
            await btn.async_press()

        api.set_light_brightness.assert_awaited_once_with("SC1_M01.Light1", 60)

    @pytest.mark.asyncio
    async def test_press_no_data_defaults(self):
        """When no data available, defaults to was_on=False, brightness=100."""
        coord = _make_coordinator()
        coord.get_entity_data = MagicMock(return_value=None)
        api = _make_api()
        btn = EvonIdentifyButton(coord, "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api)

        with patch("custom_components.evon.button.asyncio.sleep", new_callable=AsyncMock):
            await btn.async_press()

        # Default was_on=False → restore to off
        assert api.turn_off_light.await_count == 2

    @pytest.mark.asyncio
    async def test_press_api_error_raises_ha_error(self):
        api = _make_api()
        api.turn_off_light.side_effect = EvonApiError("fail")
        btn = EvonIdentifyButton(
            _make_coordinator(), "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api
        )
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError, match="Failed to identify light"):
            await btn.async_press()

    @pytest.mark.asyncio
    async def test_press_uses_animation_delay(self):
        """Verify asyncio.sleep is called with the animation delay."""
        coord = _make_coordinator()
        coord.get_entity_data = MagicMock(return_value={"is_on": False, "brightness": 0})
        api = _make_api()
        btn = EvonIdentifyButton(coord, "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api)

        with patch("custom_components.evon.button.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await btn.async_press()
            assert mock_sleep.await_count == 2
            mock_sleep.assert_any_await(LIGHT_IDENTIFY_ANIMATION_DELAY)

    @pytest.mark.asyncio
    async def test_press_brightness_clamped_to_100(self):
        """Brightness > 100 is clamped to 100 (no extra restore)."""
        coord = _make_coordinator()
        coord.get_entity_data = MagicMock(return_value={"is_on": True, "brightness": 150})
        api = _make_api()
        btn = EvonIdentifyButton(coord, "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api)

        with patch("custom_components.evon.button.asyncio.sleep", new_callable=AsyncMock):
            await btn.async_press()

        # Clamped to 100 → no brightness restore
        api.set_light_brightness.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_press_negative_brightness_clamped_to_zero(self):
        """Negative brightness clamped to 0."""
        coord = _make_coordinator()
        coord.get_entity_data = MagicMock(return_value={"is_on": True, "brightness": -5})
        api = _make_api()
        btn = EvonIdentifyButton(coord, "SC1_M01.Light1", "Living Light", "Living Room", _make_entry(), api)

        with patch("custom_components.evon.button.asyncio.sleep", new_callable=AsyncMock):
            await btn.async_press()

        # -5 clamped to 0 (which != 100) → brightness set to 0
        api.set_light_brightness.assert_awaited_once_with("SC1_M01.Light1", 0)


# =============================================================================
# Integration tests (require pytest-homeassistant-custom-component)
# =============================================================================


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_scene_button_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test scene button is created from scene device."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Scene button should exist
    state = hass.states.get("button.all_lights_off")
    assert state is not None


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_scene_button_press(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test pressing scene button calls execute_scene API."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Press the button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.all_lights_off"},
        blocking=True,
    )

    # Verify API was called
    mock_evon_api_class.execute_scene.assert_called_once_with("SceneApp1234")
