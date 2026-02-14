"""Tests for brightness conversion edge cases (C-M5)."""

from __future__ import annotations


class TestEvonToHABrightness:
    """Test Evon (0-100) to HA (0-255) brightness conversion.

    The conversion formula in light.py is:
        int(evon_brightness * 255 / 100)
    """

    def _evon_to_ha(self, evon_brightness: int) -> int:
        """Convert Evon brightness (0-100) to HA brightness (0-255)."""
        return int(evon_brightness * 255 / 100)

    def test_zero_maps_to_zero(self):
        """Test Evon 0 -> HA 0."""
        assert self._evon_to_ha(0) == 0

    def test_100_maps_to_255(self):
        """Test Evon 100 -> HA 255."""
        assert self._evon_to_ha(100) == 255

    def test_1_maps_to_2(self):
        """Test Evon 1 -> HA 2 (lowest non-zero)."""
        assert self._evon_to_ha(1) == 2

    def test_50_maps_to_127(self):
        """Test Evon 50 -> HA 127 (midpoint)."""
        assert self._evon_to_ha(50) == 127

    def test_75_maps_to_191(self):
        """Test Evon 75 -> HA 191 (matches mock data in conftest)."""
        assert self._evon_to_ha(75) == 191

    def test_99_maps_to_252(self):
        """Test Evon 99 -> HA 252 (just below max)."""
        assert self._evon_to_ha(99) == 252


class TestHAToEvonBrightness:
    """Test HA (0-255) to Evon (0-100) brightness conversion.

    The conversion formula in light.py async_turn_on is:
        max(0, min(100, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)))
    """

    def _ha_to_evon(self, ha_brightness: int) -> int:
        """Convert HA brightness (0-255) to Evon brightness (0-100)."""
        return max(0, min(100, round(ha_brightness * 100 / 255)))

    def test_0_maps_to_0(self):
        """Test HA 0 -> Evon 0."""
        assert self._ha_to_evon(0) == 0

    def test_255_maps_to_100(self):
        """Test HA 255 -> Evon 100."""
        assert self._ha_to_evon(255) == 100

    def test_1_maps_to_0(self):
        """Test HA 1 -> Evon 0 (rounds down from 0.39)."""
        assert self._ha_to_evon(1) == 0

    def test_254_maps_to_100(self):
        """Test HA 254 -> Evon 100 (rounds up from 99.6)."""
        assert self._ha_to_evon(254) == 100

    def test_2_maps_to_1(self):
        """Test HA 2 -> Evon 1 (rounds to 0.78 -> 1)."""
        assert self._ha_to_evon(2) == 1

    def test_3_maps_to_1(self):
        """Test HA 3 -> Evon 1 (rounds to 1.18 -> 1)."""
        assert self._ha_to_evon(3) == 1

    def test_128_maps_to_50(self):
        """Test HA 128 -> Evon 50 (midpoint rounds to 50.2 -> 50)."""
        assert self._ha_to_evon(128) == 50

    def test_127_maps_to_50(self):
        """Test HA 127 -> Evon 50 (midpoint rounds to 49.8 -> 50)."""
        assert self._ha_to_evon(127) == 50


class TestRoundtripConsistency:
    """Test that round-trip conversions are within the tolerance."""

    def _evon_to_ha(self, evon: int) -> int:
        return int(evon * 255 / 100)

    def _ha_to_evon(self, ha: int) -> int:
        return max(0, min(100, round(ha * 100 / 255)))

    def test_roundtrip_evon_to_ha_to_evon(self):
        """Test that Evon -> HA -> Evon is within tolerance of 1."""

        for evon_val in range(101):
            ha_val = self._evon_to_ha(evon_val)
            roundtrip = self._ha_to_evon(ha_val)
            assert abs(roundtrip - evon_val) <= 1, (
                f"Roundtrip failed: Evon {evon_val} -> HA {ha_val} -> Evon {roundtrip}"
            )

    def test_optimistic_state_tolerance_covers_rounding(self):
        """Test that OPTIMISTIC_STATE_TOLERANCE (2) covers worst-case rounding."""
        from custom_components.evon.const import OPTIMISTIC_STATE_TOLERANCE

        for evon_val in range(101):
            ha_val = self._evon_to_ha(evon_val)
            # Simulate: user sets HA brightness, Evon reports back
            roundtrip_evon = self._ha_to_evon(ha_val)
            roundtrip_ha = self._evon_to_ha(roundtrip_evon)
            diff = abs(roundtrip_ha - ha_val)
            assert diff <= OPTIMISTIC_STATE_TOLERANCE, (
                f"Tolerance exceeded: ha={ha_val}, roundtrip={roundtrip_ha}, diff={diff}"
            )
