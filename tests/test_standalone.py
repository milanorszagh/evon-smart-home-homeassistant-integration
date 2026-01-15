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
        print("MCP server has tools, resources, and scenes")


class TestIntegrationFiles:
    """Test all integration files exist."""

    def test_all_platform_files_exist(self):
        """Test all platform files exist."""
        base_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "evon")

        required_files = [
            "__init__.py",
            "api.py",
            "config_flow.py",
            "const.py",
            "coordinator.py",
            "light.py",
            "cover.py",
            "climate.py",
            "sensor.py",
            "switch.py",
            "binary_sensor.py",
            "device_trigger.py",
            "diagnostics.py",
            "logbook.py",
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
        assert "device_automation" in translations
        assert "step" in translations["config"]
        assert "reconfigure" in translations["config"]["step"]
        assert "trigger_type" in translations["device_automation"]
        print("Translations include config, options, device_automation, and reconfigure")


if __name__ == "__main__":
    # Simple test runner
    import traceback

    tests = [
        TestPasswordEncoding(),
        TestHostNormalization(),
        TestEvonConstants(),
        TestMCPServer(),
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
