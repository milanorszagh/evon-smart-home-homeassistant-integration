"""Standalone tests that don't require Home Assistant."""

from __future__ import annotations

import os
import sys

# Add custom_components to path for direct import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPasswordEncoding:
    """Test password encoding without HA dependencies."""

    def test_encode_password(self):
        """Test password encoding matches expected format."""
        import base64
        import hashlib

        def encode_password(username: str, password: str) -> str:
            combined = username + password
            sha512_hash = hashlib.sha512(combined.encode("utf-8")).digest()
            return base64.b64encode(sha512_hash).decode("utf-8")

        # Test with known values
        username = "TestUser"
        password = "test_password_123"
        encoded = encode_password(username, password)

        # Should be 88 characters (base64 encoded SHA512)
        assert len(encoded) == 88
        assert encoded.endswith("==")
        print(f"Encoded password: {encoded[:20]}...{encoded[-10:]}")

    def test_encoding_consistency(self):
        """Test that encoding is consistent."""
        import base64
        import hashlib

        def encode_password(username: str, password: str) -> str:
            combined = username + password
            sha512_hash = hashlib.sha512(combined.encode("utf-8")).digest()
            return base64.b64encode(sha512_hash).decode("utf-8")

        encoded1 = encode_password("user", "pass")
        encoded2 = encode_password("user", "pass")
        assert encoded1 == encoded2

    def test_different_inputs_different_outputs(self):
        """Test that different inputs produce different outputs."""
        import base64
        import hashlib

        def encode_password(username: str, password: str) -> str:
            combined = username + password
            sha512_hash = hashlib.sha512(combined.encode("utf-8")).digest()
            return base64.b64encode(sha512_hash).decode("utf-8")

        encoded1 = encode_password("user1", "pass")
        encoded2 = encode_password("user2", "pass")
        assert encoded1 != encoded2


class TestHostNormalization:
    """Test host URL normalization."""

    def test_ip_only(self):
        """Test IP address without protocol."""
        from urllib.parse import urlparse

        def normalize_host(host: str) -> str:
            host = host.strip()
            if not host.startswith(("http://", "https://")):
                host = f"http://{host}"
            parsed = urlparse(host)
            return f"{parsed.scheme}://{parsed.netloc}"

        assert normalize_host("192.168.1.4") == "http://192.168.1.4"
        print("IP only: 192.168.1.4 -> http://192.168.1.4")

    def test_ip_with_port(self):
        """Test IP address with port."""
        from urllib.parse import urlparse

        def normalize_host(host: str) -> str:
            host = host.strip()
            if not host.startswith(("http://", "https://")):
                host = f"http://{host}"
            parsed = urlparse(host)
            return f"{parsed.scheme}://{parsed.netloc}"

        assert normalize_host("192.168.1.4:8080") == "http://192.168.1.4:8080"
        print("IP with port: 192.168.1.4:8080 -> http://192.168.1.4:8080")

    def test_full_url(self):
        """Test full URL passes through."""
        from urllib.parse import urlparse

        def normalize_host(host: str) -> str:
            host = host.strip()
            if not host.startswith(("http://", "https://")):
                host = f"http://{host}"
            parsed = urlparse(host)
            return f"{parsed.scheme}://{parsed.netloc}"

        assert normalize_host("http://192.168.1.4") == "http://192.168.1.4"
        print("Full URL: http://192.168.1.4 -> http://192.168.1.4")

    def test_trailing_slash(self):
        """Test trailing slash is removed."""
        from urllib.parse import urlparse

        def normalize_host(host: str) -> str:
            host = host.strip()
            if not host.startswith(("http://", "https://")):
                host = f"http://{host}"
            parsed = urlparse(host)
            return f"{parsed.scheme}://{parsed.netloc}"

        assert normalize_host("http://192.168.1.4/") == "http://192.168.1.4"
        print("Trailing slash: http://192.168.1.4/ -> http://192.168.1.4")

    def test_https(self):
        """Test HTTPS is preserved."""
        from urllib.parse import urlparse

        def normalize_host(host: str) -> str:
            host = host.strip()
            if not host.startswith(("http://", "https://")):
                host = f"http://{host}"
            parsed = urlparse(host)
            return f"{parsed.scheme}://{parsed.netloc}"

        assert normalize_host("https://192.168.1.4") == "https://192.168.1.4"
        print("HTTPS: https://192.168.1.4 -> https://192.168.1.4")

    def test_whitespace(self):
        """Test whitespace is trimmed."""
        from urllib.parse import urlparse

        def normalize_host(host: str) -> str:
            host = host.strip()
            if not host.startswith(("http://", "https://")):
                host = f"http://{host}"
            parsed = urlparse(host)
            return f"{parsed.scheme}://{parsed.netloc}"

        assert normalize_host("  192.168.1.4  ") == "http://192.168.1.4"
        print("Whitespace: '  192.168.1.4  ' -> http://192.168.1.4")


class TestEvonConstants:
    """Test constants are properly defined."""

    def test_device_classes_exist(self):
        """Test that device class constants exist."""
        # These should match the Evon API class names
        expected_classes = {
            "LIGHT_DIM": "SmartCOM.Light.LightDim",
            "LIGHT": "SmartCOM.Light.Light",
            "BLIND": "SmartCOM.Blind.Blind",
            "CLIMATE": "SmartCOM.Clima.ClimateControl",
        }

        # Read const.py to verify
        const_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "const.py")

        with open(const_path) as f:
            content = f.read()

        for name, value in expected_classes.items():
            assert value in content, f"Missing class {name} = {value}"
            print(f"Found: {name} = {value}")

    def test_climate_preset_modes(self):
        """Test climate preset modes use HA built-in names for icons."""
        const_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "const.py")

        with open(const_path) as f:
            content = f.read()

        # Should use HA built-in preset names
        assert 'CLIMATE_MODE_COMFORT = "comfort"' in content, "Missing comfort preset"
        assert 'CLIMATE_MODE_ENERGY_SAVING = "eco"' in content, "Energy saving should be 'eco' for HA icon"
        assert 'CLIMATE_MODE_FREEZE_PROTECTION = "away"' in content, "Freeze protection should be 'away' for HA icon"
        print("Climate presets use HA built-in names: comfort, eco, away")


class TestMCPServer:
    """Test MCP server TypeScript compiles."""

    def test_typescript_compiled(self):
        """Test that TypeScript is compiled."""
        dist_path = os.path.join(os.path.dirname(__file__), "..", "dist", "index.js")
        assert os.path.exists(dist_path), "dist/index.js not found - run npm run build"

        # Check file is not empty
        size = os.path.getsize(dist_path)
        assert size > 1000, f"dist/index.js seems too small ({size} bytes)"
        print(f"dist/index.js: {size} bytes")

    def test_source_exists(self):
        """Test source file exists."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "src", "index.ts")
        assert os.path.exists(src_path), "src/index.ts not found"

        with open(src_path) as f:
            content = f.read()

        # Check for key features
        assert "server.tool" in content, "No tools defined"
        assert "server.resource" in content, "No resources defined"
        assert "scenes" in content.lower(), "No scenes support"
        assert "home_state" in content.lower() or "homestate" in content.lower(), "No home state support"
        print("MCP server has tools, resources, scenes, and home states")


class TestOptimisticUpdates:
    """Test that optimistic updates are implemented in entity files."""

    def test_light_has_optimistic_updates(self):
        """Test light.py has optimistic update pattern."""
        light_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "light.py")

        with open(light_path) as f:
            content = f.read()

        assert "_optimistic_is_on" in content, "Light missing _optimistic_is_on"
        assert "_optimistic_brightness" in content, "Light missing _optimistic_brightness"
        assert "_handle_coordinator_update" in content, "Light missing _handle_coordinator_update"
        print("Light has optimistic updates: is_on, brightness")

    def test_cover_has_optimistic_updates(self):
        """Test cover.py has optimistic update pattern."""
        cover_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "cover.py")

        with open(cover_path) as f:
            content = f.read()

        assert "_optimistic_position" in content, "Cover missing _optimistic_position"
        assert "_optimistic_tilt" in content, "Cover missing _optimistic_tilt"
        assert "_handle_coordinator_update" in content, "Cover missing _handle_coordinator_update"
        print("Cover has optimistic updates: position, tilt")

    def test_climate_has_optimistic_updates(self):
        """Test climate.py has optimistic update pattern."""
        climate_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "climate.py")

        with open(climate_path) as f:
            content = f.read()

        assert "_optimistic_preset" in content, "Climate missing _optimistic_preset"
        assert "_optimistic_target_temp" in content, "Climate missing _optimistic_target_temp"
        assert "_optimistic_hvac_mode" in content, "Climate missing _optimistic_hvac_mode"
        assert "_handle_coordinator_update" in content, "Climate missing _handle_coordinator_update"
        print("Climate has optimistic updates: preset, target_temp, hvac_mode")

    def test_switch_has_optimistic_updates(self):
        """Test switch.py has optimistic update pattern."""
        switch_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "switch.py")

        with open(switch_path) as f:
            content = f.read()

        assert "_optimistic_is_on" in content, "Switch missing _optimistic_is_on"
        assert "_handle_coordinator_update" in content, "Switch missing _handle_coordinator_update"
        # Should have optimistic for both EvonSwitch and EvonBathroomRadiatorSwitch
        assert content.count("_optimistic_is_on: bool | None = None") >= 2, (
            "Both switch types should have optimistic updates"
        )
        print("Switch has optimistic updates: is_on (both regular and bathroom radiator)")

    def test_select_has_optimistic_updates(self):
        """Test select.py has optimistic update pattern."""
        select_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "select.py")

        with open(select_path) as f:
            content = f.read()

        assert "_optimistic_option" in content, "Select missing _optimistic_option"
        assert "_handle_coordinator_update" in content, "Select missing _handle_coordinator_update"
        print("Select has optimistic updates: option")


class TestRepairsFeature:
    """Test repairs feature is properly implemented."""

    def test_repair_constants_exist(self):
        """Test that repair constants are defined."""
        const_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "const.py")

        with open(const_path) as f:
            content = f.read()

        assert 'REPAIR_CONNECTION_FAILED = "connection_failed"' in content
        assert 'REPAIR_STALE_ENTITIES_CLEANED = "stale_entities_cleaned"' in content
        assert 'REPAIR_CONFIG_MIGRATION = "config_migration_needed"' in content
        assert "CONNECTION_FAILURE_THRESHOLD = 3" in content
        print("Repair constants: connection_failed, stale_entities_cleaned, config_migration_needed, threshold=3")

    def test_repairs_flow_import(self):
        """Test that RepairsFlow is imported from correct module."""
        config_flow_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "config_flow.py")

        with open(config_flow_path) as f:
            content = f.read()

        assert "from homeassistant.components.repairs import RepairsFlow" in content
        assert "class EvonStaleEntitiesRepairFlow(RepairsFlow):" in content
        assert "async def async_create_fix_flow" in content
        print("RepairsFlow imported correctly, EvonStaleEntitiesRepairFlow defined")

    def test_coordinator_tracks_failures(self):
        """Test that coordinator has failure tracking for repairs."""
        coordinator_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "coordinator.py")

        with open(coordinator_path) as f:
            content = f.read()

        assert "_consecutive_failures" in content
        assert "_repair_created" in content
        assert "CONNECTION_FAILURE_THRESHOLD" in content
        assert "ir.async_create_issue" in content
        assert "ir.async_delete_issue" in content
        print("Coordinator has failure tracking: _consecutive_failures, _repair_created, creates/deletes issues")

    def test_init_has_stale_entity_repair(self):
        """Test that __init__.py creates stale entity repairs."""
        init_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "__init__.py")

        with open(init_path) as f:
            content = f.read()

        assert "_async_cleanup_stale_entities" in content
        assert "REPAIR_STALE_ENTITIES_CLEANED" in content
        assert "async_migrate_entry" in content
        assert "REPAIR_CONFIG_MIGRATION" in content
        print("__init__.py has stale entity cleanup and config migration repairs")

    def test_hub_device_created(self):
        """Test that __init__.py creates hub device for via_device references."""
        init_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "__init__.py")

        with open(init_path) as f:
            content = f.read()

        assert "device_registry = dr.async_get(hass)" in content
        assert "device_registry.async_get_or_create(" in content
        assert "identifiers={(DOMAIN, entry.entry_id)}" in content
        assert 'name="Evon Smart Home"' in content
        print("Hub device created with identifier (DOMAIN, entry.entry_id)")

    def test_repair_translations_exist(self):
        """Test that repair translations exist in both languages."""
        import json

        for lang in ["en", "de"]:
            trans_path = os.path.join(
                os.path.dirname(__file__), "..", "custom_components", "evon", "translations", f"{lang}.json"
            )

            with open(trans_path) as f:
                translations = json.load(f)

            assert "issues" in translations, f"Missing issues section in {lang}.json"
            issues = translations["issues"]
            assert "connection_failed" in issues, f"Missing connection_failed in {lang}.json"
            assert "stale_entities_cleaned" in issues, f"Missing stale_entities_cleaned in {lang}.json"
            assert "config_migration_failed" in issues, f"Missing config_migration_failed in {lang}.json"

        print("Repair translations exist in en.json and de.json")


class TestHomeStateTranslations:
    """Test home state uses HA translation system."""

    def test_no_hardcoded_translations(self):
        """Test that select.py doesn't have hardcoded HOME_STATE_TRANSLATIONS."""
        select_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "select.py")

        with open(select_path) as f:
            content = f.read()

        assert "HOME_STATE_TRANSLATIONS" not in content, "Should not have hardcoded translations"
        assert '"Daheim"' not in content, "Should not have hardcoded German names"
        assert '"At Home"' not in content, "Should not have hardcoded English names"
        print("No hardcoded home state translations in select.py")

    def test_home_state_uses_evon_ids(self):
        """Test that home state select uses Evon IDs as options."""
        select_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "select.py")

        with open(select_path) as f:
            content = f.read()

        # Should use state["id"] directly as options
        assert 'self._attr_options = [state["id"] for state in home_states]' in content
        print("Home state select uses Evon IDs as options")

    def test_home_state_translations_exist(self):
        """Test that home state translations have state entries."""
        import json

        for lang, expected_states in [
            ("en", {"HomeStateAtHome": "At Home", "HomeStateHoliday": "Holiday"}),
            ("de", {"HomeStateAtHome": "Daheim", "HomeStateHoliday": "Urlaub"}),
        ]:
            trans_path = os.path.join(
                os.path.dirname(__file__), "..", "custom_components", "evon", "translations", f"{lang}.json"
            )

            with open(trans_path) as f:
                translations = json.load(f)

            home_state = translations["entity"]["select"]["home_state"]
            assert "state" in home_state, f"Missing state translations in {lang}.json"

            for evon_id, display_name in expected_states.items():
                assert evon_id in home_state["state"], f"Missing {evon_id} in {lang}.json"
                assert home_state["state"][evon_id] == display_name, f"Wrong translation for {evon_id} in {lang}.json"

        print("Home state translations correct: en=English names, de=German names")


class TestIntegrationFiles:
    """Test all integration files exist."""

    def test_all_platform_files_exist(self):
        """Test all platform files exist."""
        base_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon")

        required_files = [
            "__init__.py",
            "api.py",
            "base_entity.py",
            "config_flow.py",
            "const.py",
            "coordinator.py",
            "light.py",
            "cover.py",
            "climate.py",
            "sensor.py",
            "switch.py",
            "select.py",
            "binary_sensor.py",
            "diagnostics.py",
            "manifest.json",
            "strings.json",
        ]

        for filename in required_files:
            filepath = os.path.join(base_path, filename)
            assert os.path.exists(filepath), f"Missing: {filename}"
            print(f"Found: {filename}")

    def test_translations_exist(self):
        """Test translations exist."""
        en_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon", "translations", "en.json")
        assert os.path.exists(en_path), "Missing English translations"

        import json

        with open(en_path) as f:
            translations = json.load(f)

        assert "config" in translations
        assert "options" in translations
        assert "entity" in translations
        assert "step" in translations["config"]
        assert "reconfigure" in translations["config"]["step"]
        assert "select" in translations["entity"]
        print("Translations include config, options, entity, and reconfigure")


if __name__ == "__main__":
    # Simple test runner
    import traceback

    tests = [
        TestPasswordEncoding(),
        TestHostNormalization(),
        TestEvonConstants(),
        TestMCPServer(),
        TestOptimisticUpdates(),
        TestRepairsFeature(),
        TestHomeStateTranslations(),
        TestIntegrationFiles(),
    ]

    passed = 0
    failed = 0

    for test_class in tests:
        print(f"\n{'=' * 60}")
        print(f"Running: {test_class.__class__.__name__}")
        print("=" * 60)

        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                try:
                    print(f"\n  {method_name}...")
                    getattr(test_class, method_name)()
                    print("  ✓ PASSED")
                    passed += 1
                except Exception as e:
                    print(f"  ✗ FAILED: {e}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
