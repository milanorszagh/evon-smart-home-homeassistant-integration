"""Translation consistency tests (no Home Assistant framework required).

hassfest only validates strings.json and translations/en.json; these tests keep
the other nine languages in lock-step and make sure values that reach the UI
through selectors or enum states are translatable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

COMPONENT_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "evon"
STRINGS = json.loads((COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
TRANSLATION_FILES = sorted((COMPONENT_DIR / "translations").glob("*.json"))
TRANSLATIONS = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in TRANSLATION_FILES}
SERVICES = yaml.safe_load((COMPONENT_DIR / "services.yaml").read_text(encoding="utf-8"))


def _leaf_paths(node: dict, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths |= _leaf_paths(value, path)
        else:
            paths.add(path)
    return paths


def _select_fields() -> list[tuple[str, str, dict]]:
    """Return (service, field, selector) for every select selector with options."""
    found = []
    for service, definition in SERVICES.items():
        for field, spec in (definition.get("fields") or {}).items():
            select = (spec.get("selector") or {}).get("select")
            if select and select.get("options"):
                found.append((service, field, select))
    assert found, "expected at least one select selector in services.yaml"
    return found


def test_translation_files_cover_all_languages():
    assert set(TRANSLATIONS) == {"cs", "de", "en", "es", "fr", "it", "pl", "pt", "sk", "sl"}


def test_en_matches_strings():
    assert TRANSLATIONS["en"] == STRINGS


@pytest.mark.parametrize("lang", sorted(TRANSLATIONS))
def test_every_language_has_exactly_the_strings_keys(lang):
    expected = _leaf_paths(STRINGS)
    actual = _leaf_paths(TRANSLATIONS[lang])
    assert actual == expected, f"{lang}: missing={sorted(expected - actual)} extra={sorted(actual - expected)}"


@pytest.mark.parametrize(("service", "field", "select"), _select_fields())
def test_service_select_options_are_translatable(service, field, select):
    """Select selectors with fixed options must carry a translation_key, and
    every language must label every option (otherwise the UI shows raw values)."""
    key = select.get("translation_key")
    assert key, f"{service}.{field}: select selector has no translation_key"
    for lang, data in TRANSLATIONS.items():
        labels = data.get("selector", {}).get(key, {}).get("options", {})
        assert set(labels) == set(select["options"]), f"{lang}: selector.{key}.options mismatch"


@pytest.mark.parametrize(
    ("selector_key", "entity_key"),
    [("home_state", "home_state"), ("season_mode", "season_mode")],
)
def test_service_option_labels_match_select_entity_states(selector_key, entity_key):
    """The action dropdown and the select entity must use the same wording."""
    for lang, data in TRANSLATIONS.items():
        option_labels = data["selector"][selector_key]["options"]
        state_labels = data["entity"]["select"][entity_key]["state"]
        assert option_labels == state_labels, f"{lang}: selector.{selector_key} vs entity.select.{entity_key}.state"


def test_websocket_status_sensor_states_are_translated():
    for lang, data in TRANSLATIONS.items():
        states = data["entity"]["sensor"]["websocket_status"].get("state", {})
        assert set(states) == {"connected", "disconnected", "disabled"}, f"{lang}: websocket_status states"
        assert all(value.strip() for value in states.values()), f"{lang}: empty websocket_status state label"
