# Changelog

All notable changes to the Evon Smart Home integration and the bundled MCP server.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); every
version corresponds to a git tag and a GitHub release (1.8.2 has a tag but no release).
Besides the standard section names (Added, Changed, Deprecated, Removed, Fixed, Security)
two more are used: **Breaking changes** for anything that needs action after upgrading,
and **Project** for CI, tooling and repository changes that do not affect what gets
installed. The README keeps a one-line summary per version.

Issue and PR numbers refer to this repository unless stated otherwise.

## [Unreleased]

### Fixed

- **Clean shutdown on Home Assistant restart.** Home Assistant does not unload config
  entries when it stops, so the integration kept its WebSocket loop and polling alive
  until HA closed its shared HTTP session. Every restart then logged three
  `Session is closed and no session factory available` tracebacks, opened a spurious
  "WebSocket disconnected" repair issue and ran one more full poll that delayed the
  shutdown by up to a poll cycle. The integration now stops polling and closes the
  WebSocket as soon as HA announces it is stopping, a WebSocket drop that arrives while
  HA is stopping is no longer treated as a failure, and the error for a closed session
  names the actual cause.

## [1.23.0] - 2026-10-12

### Breaking changes

- **Minimum Home Assistant version is now 2026.8.0** (was 2026.5.0). 2026.8 is the first
  release whose device registry accepts the `via_device_id` link that replaces the
  deprecated `via_device` tuple. The floor lives in `hacs.json`; the key was removed from
  `manifest.json` because hassfest rejects it there.
- **Home State select option values changed** from the raw Evon IDs (`HomeStateAtHome`,
  `HomeStateNight`, `HomeStateWork`, `HomeStateHoliday`) to `at_home`, `night`, `work`,
  `holiday`, the same names the `evon.set_home_state` action already uses. Reason: Home
  Assistant's hassfest validator requires translation keys to match `[a-z0-9-_]+`.
  - State conditions and dashboards that compare against the old values must be updated
    (the old values keep working for now, see *Deprecated* below).
  - The raw Evon ID remains available in the entity's `evon_id` attribute.
  - Two Evon states that derive the same option key (for example `HomeStateAt_Home` and
    `HomeStateAtHome`) are reported once in the log; the first one wins.

### Deprecated

- The raw Evon IDs (`HomeStateAtHome`, ...) are still accepted by `select.select_option`
  on the Home State select, with a warning in the log that names the replacement.
  Planned removal: 1.25.0.

### Fixed

- **Home Assistant deprecation warnings removed.** Running the test suite against HA
  2026.10.1 surfaced several deprecated calls, all fixed and now guarded by a test fixture
  that fails any test during which HA reports deprecated API usage by this integration:
  - Devices link to the hub by registry id (`via_device_id`). HA 2026.9 and newer logged
    *"deprecated `via_device` parameter … please create a bug report"* for every Evon
    device at startup; that path would have broken in HA 2027.8.
  - Reconfigure and re-authentication no longer reload the entry themselves (HA reports
    that as deprecated for integrations with an update listener; breaks in HA 2026.12).
    The update listener now reloads on data changes, and re-entering unchanged credentials
    still reloads the integration.
  - Device triggers no longer read the deprecated `DeviceEntry.config_entries`; two
    controllers sharing an instance id can no longer answer for each other.
  - CO2 sensor uses `UnitOfRatio.PARTS_PER_MILLION` instead of the deprecated constant.
- **WebSocket:** a `CLOSE` or `CLOSING` frame from the Evon controller now triggers a clean
  disconnect and reconnect instead of being ignored (#11).
- Energy statistics import returns early when the recorder integration is not loaded
  instead of raising inside a background task.
- **Camera recordings are saved inside Home Assistant's local media folder** (`/media`
  on Home Assistant OS and Docker, `<config>/media` on venv installs), which is where the
  media browser and the card's "All Recordings" link look. Earlier versions always wrote
  to `<config>/media/evon_recordings`, a folder the media browser does not show on HAOS.
  Existing recordings are moved to the new location once at startup.
- **MCP server:** the WebSocket light helpers now send the `SwitchOn` / `SwitchOff` /
  `BrightnessSetScaled` commands the controller acts on instead of property writes that
  were acknowledged but ignored.
- **MCP server:** dead WebSocket connections are detected with a ping/pong heartbeat
  (30 s interval, 10 s grace) and reconnected, instead of hanging until restart (#12).
- **MCP server:** dotenv's "injected env" startup message no longer goes to stdout when a
  `.env` file is present in the working directory, which could corrupt the MCP protocol
  stream. dotenv was bumped to 18 and configured quiet.

### Changed

- **Translations:** the option dropdowns of the `evon.set_home_state` and
  `evon.set_season_mode` actions and the states of the WebSocket Status sensor are now
  translated in all 10 languages. They showed raw values like `at_home` or `connected`
  before. Service values and sensor state values are unchanged, so existing automations
  are unaffected.
- All remote-access URLs derive from one constant, so a future move of the relay host
  (`my.evon-smarthome.com`) is a one-line change.
- Helper scripts: `scripts/ha-logs.sh` reads the whole current journal
  (`HA_LOG_JOURNAL_LINES`, default 300000 lines) instead of the 100 lines `ha core logs`
  returns by default, which with debug logging enabled covered only a few seconds, and
  strips ANSI colour codes before filtering. Both `ha-deploy.sh` and `ha-logs.sh` honour
  `HA_SSH_KEY` from `.env` (default `~/.ssh/claude_code`).
- README links to Schrack Technik, the new home of evon Smart Home (the product is being
  renamed *Schrack Smart Building*). Nothing changes for the integration.

### Project

- Home Assistant's hassfest validator runs in CI, also on release tags (#14); the manifest
  declares `http` as a dependency and `recorder` as an after-dependency.
- `hacs/action` and `hassfest` are pinned by commit (#13).
- npm security audit is clean again: 7 advisories in transitive MCP server dependencies,
  including one critical, all resolved within the existing version ranges.
- Test harness moved to HA 2026.10.1; GitHub Actions bumped to current majors
  (checkout, setup-python, setup-node, codecov v7; codeql-action v4).
- Renovate is active (it had been running in Mend's silent mode): weekend schedule, patch
  updates automerge on green CI, TypeScript 7 and `@types/node` 25 and newer held
  (`allowedVersions: "<25"`), CI Python version excluded.
- Held on purpose: TypeScript 7 (typescript-eslint does not support it yet), `@types/node`
  25 and newer (Node 24 floor), the climate `native_*` temperature rename (lands in HA
  2026.11).
- The relay-host guard test compares parsed hostnames (`urlsplit(...).hostname`) instead
  of URL substrings, resolving a CodeQL `py/incomplete-url-substring-sanitization` alert.
- This file: CHANGELOG.md introduced in Keep a Changelog format. The detailed version
  history moved out of README.md (which keeps a compact table) and AGENTS.md, and the
  GitHub release notes are now taken from the version's section here.
- Test suite: 1322 Python tests and 21 MCP tests. New `tests/test_translations.py` keeps
  all 10 languages key-for-key in sync with `strings.json`.

## [1.22.1] - 2026-08-24

### Fixed

- **Quiet systems no longer disconnect every 3 minutes.** The 180 s timeout around each
  WebSocket `receive()` call expired on perfectly healthy connections: aiohttp answers
  server pings internally, so a quiet connection legitimately produces no frames. The
  result was a spurious ERROR log, a full teardown and reconnect every 3 minutes, a
  flapping "WebSocket disconnected" repair notification, and in-flight commands failing
  during each flap. The timeout is gone; dead connections are still detected by the 30 s
  aiohttp heartbeat, now pinned by a regression test.
  Diagnosis and fix by Gernot Reisinger (@Hollerberg) in #6, merged via #10.

### Changed

- `@types/node` realigned to the Node 24 floor so TypeScript checks against the runtime
  the package advertises.
- Dead `[tool.pytest.ini_options]` block removed from `pyproject.toml`; the root
  `pytest.ini` is authoritative.
- Release recipe stages the changelog files; nonexistent `info.md` dropped from checklists.
- Test suite: 1276 tests.

## [1.22.0] - 2026-08-07

### Breaking changes

- **Minimum Home Assistant version 2026.5.0**, which itself requires Python 3.14.2+. The
  bundled MCP server requires Node.js 24 LTS. The source contains 3.14-only syntax, so an
  older interpreter fails with a `SyntaxError`; this affects nobody who can run HA 2026.x.
  This also fixed a silent test gap: with an open version floor the test harness resolved
  to HA 2025.1.4 under Python 3.12, so the suite had never exercised a supported release.

### Changed

- **Post-command behaviour redesigned.** The old "command, optimistic state, immediate
  HTTP recheck" pattern is replaced by a 5 s quiet window that any incoming WebSocket
  event cancels. This removes the bounce-back where the UI briefly flipped back to the
  stale "on" state after turning a light off, and cuts HTTP load on the controller.
  Climate gained a self-healing recheck fallback; the bathroom radiator's 3 s verify timer
  is gone.
- Coordinator uses `async_update_listeners()` for WebSocket events, so real-time updates
  no longer reset the polling timer.
- Dimmable lights report brightness 0 instead of a stale value when off.
- MCP server: `validateConfig()` replaced by `requireEvonHost()`; npm dependencies updated
  and remaining audit findings resolved.

### Security

- Camera recordings are served through an authenticated endpoint instead of an open
  static path. Footage was previously downloadable by anyone who could reach the HA port,
  including over a remote URL.

### Fixed

- WebSocket updates arriving during a slow in-flight poll are no longer overwritten by the
  poll's stale snapshot (a toggled light no longer reverted for ~20 s).
- Energy statistics import respects its 1-hour rate limit again.
- WebSocket reconnect applies backoff when the post-connect handshake fails (was a tight
  retry loop); resubscribe retries after a dropped subscription; unsubscribe while offline
  is honoured; malformed close/error frames log the real reason.
- Repair "Fix" flows moved to `repairs.py` so Home Assistant can discover them.
- Physical-button event entities no longer drop a press after a safety-net poll.
- Stuck optimistic state for light colour temperature and cover toggle-stop is cleared by
  the 30 s backstop.
- Config-entry unload no longer leaves a half-torn-down entry when platform unload fails.
- A wrong password at startup opens the re-authentication dialog, while a transient login
  rate-limit retries instead of prompting for credentials.
- Stale-entity cleanup no longer deletes entities over a transient fetch error or
  mis-truncates instance IDs containing underscores.
- Diagnostics download redacts the host / Engine ID in the config-entry title.
- Camera-recording finalize guarded against a double-encode race; instance-ID and
  image-path input validation hardened.
- Saving integration options no longer pops a phantom "WebSocket disconnected" repair.
- A WebSocket confirmation racing the command response counts as liveness, so relays no
  longer trigger a redundant full poll after every toggle; smart-meter chatter no longer
  spawns a no-op statistics task every few seconds; concurrent first refreshes are
  serialized; bulk services share the API layer's instance-ID validation.

### Project

- CI runs Python 3.14 against HA 2026.8.0; codecov-action v6; deploy script uses a
  dedicated SSH key. Test suite: 1277 tests.

## [1.21.0] - 2026-03-24

### Changed

- Minimum Home Assistant version 2026.3.0.
- MCP server covers all four HTTP light class types (`SmartCOM.Light.Light`, `LightDim`,
  `DynamicRGBWLight`, `LightGroup`).
- SSL context creation moved off the event loop; API client uses the HA-managed session.
- Repair notifications are scoped per config entry and auto-resolved.
- `py.typed` marker added.

### Fixed

- Re-authentication failures trigger Home Assistant's reauth UI.
- WebSocket disconnect raises a Repair notification.
- Three CodeQL findings resolved; flatted prototype-pollution vulnerability (high) patched.

## [1.20.0] - 2026-02-22

### Breaking changes

- **Relay outputs are light entities.** Evon relay modules (`SmartCOM.Light.Light`, L1144 /
  L1244) are exposed as on/off lights instead of switches. Existing `switch.*` entities
  for relay outputs become `light.*` entities; the old entities are removed automatically
  with a Repair notification asking you to update automations and dashboards.

### Fixed

- WebSocket race during shutdown (client captured before use).
- Climate and cover entities ignore coordinator updates during control actions, matching
  lights and switches; cover blind cache always updates first.
- Brightness 1 maps to 1 % instead of 0 %.
- Camera image fetch retries after 302/401.
- WebSocket client refuses to connect after `stop()` cleared the password.
- Config flow accepts IPv6 hosts.
- Options flow only lists dimmable lights as candidates for the non-dimmable override, and
  skips the reload when only debug flags changed.
- Diagnostics include button events and home states.

### Changed

- Named constants replace hardcoded class strings; `Base.bSwitch` dead code removed.
- AGENTS.md gained the "Architecture Decisions (Do Not Change)" section.
- Test suite: 1160 tests.

### Project

- npm audit clean again: eslint 10 and a `minimatch` override (`>=10.2.1`) for a
  high-severity ReDoS advisory; a ruff formatting failure in CI fixed.

## [1.19.2] - 2026-02-21

### Fixed

- Double-click detection for the fourth button pattern. The Evon controller sometimes
  swallows the first press-down and sends `False, True, False` instead of
  `True, False, True, False`; this was detected as a single press. Confirmed with a raw
  WebSocket capture on hardware.

## [1.19.1] - 2026-02-21

### Fixed

- **Switch (relay) 401 errors (#1).** Relay switches were the only entity type still forced
  to HTTP-only control after the WebSocket-native method rename, so they alone were
  exposed to HTTP auth token issues. They now use `SwitchOn` / `SwitchOff` over WebSocket
  like lights.
- Login backoff cap reduced from 5 minutes to 1 minute.

### Changed

- Physical buttons (`SmartCOM.Switch`) removed from the control mappings; they are
  event-only. Documentation clarifies relay vs. physical button naming.

## [1.19.0] - 2026-02-17

### Added

- **Physical wall buttons (Taster) as event entities** with single, double and long press
  detection. WebSocket-only. Device triggers for all three press types, plus the
  `evon_button_press` bus event for automations.
- Configurable double-click detection delay (0.2 to 1.4 s, default 0.8 s) in the
  integration options, shown only when buttons are detected.
- WebSocket control mappings for blind group commands (`OpenAll`, `CloseAll`, `StopAll`).
- Translations for all 10 languages.

### Fixed

- Stale-entity cleanup no longer removes button entities.
- Statistics calls run on the recorder executor.

## [1.18.0] - 2026-02-15

### Fixed

- **Auth retry storm (#2)** that caused 700+ API requests per minute on network errors:
  login backoff on network errors, re-authentication wrapped so a failed login cannot
  cascade into `token=None` requests, WebSocket receive timeout relaxed from 90 s to
  180 s (the timeout was removed entirely in 1.22.1).

### Added

- WebSocket diagnostic sensors: connection status with reconnect count, message and
  request counts, uptime, pending requests, last error and average response time; a
  latency sensor with long-term statistics.
- Doorbell event entity for 2N intercoms (native Home Assistant event entity).
- Eight new translations: French, Italian, Slovenian, Spanish, Portuguese, Polish, Czech,
  Slovak.

### Changed

- Energy statistics: `statistics_during_period` is queried once for all smart meters per
  refresh instead of once per meter.
- Coordinator: WebSocket value-change callbacks copy an entity's data before mutating it
  (copy-on-write), so a poll on the same loop tick can no longer read a half-written
  entity.
- Fourteen top-priority findings of a deep code analysis: `SERVICE_*` and
  `HOME_STATE_MAP` constants moved to `const.py`; the `recording_finished` event no longer
  reports 0 frames; the camera recorder's frame buffer is capped (`deque(maxlen=7200)`);
  O(1) entity lookup in the coordinator; the MCP server checks `EVON_HOST` at startup,
  fixes a subscription leak in `getPropertyValues`, rejects pending requests on a
  post-connection error and detects re-authentication failure in the API client retry;
  CI gained a coverage threshold and tautological test assertions were fixed.
- Further review fixes: bathroom radiator race condition, unload safety, energy entity
  lookup, blocking I/O in entity data access, TypeScript hardening and API validation.
- MCP server WebSocket client: `sequenceId` resets on reconnect; subscriptions are
  re-registered after a reconnect; `connect()` aborts cleanly when `disconnect()` is
  called mid-connect; the server exits with code 1 on fatal errors and shuts down cleanly
  on SIGTERM/SIGINT; the blind, climate, home-state and bathroom-radiator helpers use
  `CallMethod` instead of `SetValue` writes that only updated the UI.

### Project

- CodeQL security scanning for Python and JavaScript/TypeScript (push, PR, weekly) with
  CI and Codecov badges; Renovate configuration for automated dependency updates; CI
  gained pip caching, a `pip-audit` step and a macOS job in the test matrix, and surfaces
  Codecov upload failures.
- GitHub Actions bumped, test dependencies cleaned up, ruff formatting applied.
  Test suite: about 270 new tests (1,136 test functions at the tag, up from 874).

## [1.17.1] - 2026-02-11

### Fixed

- Eight bugs from a three-round code quality audit: light brightness rounding (brightness
  2 became off), climate cooling-mode temperature range, diagnostics crash on partial
  teardown, select entity error on unknown option, device trigger dict access, config flow
  accepting IPv4 octets above 255, config flow port parsing, camera recorder crash on a
  corrupt first frame.

### Changed

- WebSocket client hardened: periodic stale-request cleanup, stack traces on errors,
  fire-and-forget send errors raised, `sequenceId` validation, defensive subscription-list
  copies.
- All service handlers validate their inputs; recording duration clamped to 30 to 3600 s.
- Shared SavedPictures transformation; processors skip instances with empty IDs.
- Test suite: 994 tests (260+ new).

## [1.17.0] - 2026-02-08

### Added

- **Camera recording** for 2N intercom cameras: snapshot-based MP4 recording with
  timestamp overlay, `evon.start_recording` / `evon.stop_recording` actions, a recording
  switch entity, configurable maximum duration and output format, and recordings in the
  Home Assistant media browser.
- Custom `evon-camera-recording-card` Lovelace card with record button, live stopwatch and
  inline playback.

### Fixed

- Code quality audit follow-ups: filesystem caching, timezone-aware datetimes, migration
  robustness, deprecated API cleanup.

## [1.16.0] - 2026-02-07

### Added

- **Energy Today** and **Energy This Month** sensors, calculated from Home Assistant
  statistics and Evon's daily data. No manual `utility_meter` configuration needed.
- Group climate actions: `all_climate_comfort`, `all_climate_eco`, `all_climate_away`.
- Debug logging options.
- MCP server unit tests (`tests-mcp/`) with CI coverage.

### Fixed

- Climate WebSocket updates subscribe to setpoint limits and recompute preset
  temperatures, avoiding stale clamping.
- WebSocket error handling logs stack traces and separates expected network errors from
  unexpected failures; MCP WebSocket calls retry once after a reconnect.

## [1.15.0] - 2026-02-02

### Added

- **Camera and doorbell snapshots:** live feed from 2N intercom cameras over WebSocket,
  doorbell snapshot history as image entities (up to 10), security door sensors with a
  call-in-progress indicator.

### Changed

- Parallel data processing for faster refreshes.
- Security hardening: credentials removed from diagnostics, tokens removed from logs,
  session management hardened, WebSocket reconnect jitter, stricter input validation.

## [1.14.3] - 2026-02-02

### Fixed

- Climate target temperature over WebSocket uses `CallMethod WriteCurrentSetTemperature`
  instead of `SetValue SetTemperature`, which only updated the displayed value and never
  reached the thermostat.

The tags `v1.14.2` and `v1.14.3` both point at the same commit (358fdec, 2026-02-06),
which lies after `v1.15.0` in the history; the compare links therefore span more than
these two fixes.

## [1.14.2] - 2026-02-02

### Fixed

- `Heating.ClimateControlUniversal` devices use WebSocket control: the class-name
  constant was `ClimateControlUniversal`, so preset changes on these devices fell back to
  HTTP.

## [1.14.1] - 2026-02-02

### Added

- Integration actions: `evon.refresh`, `evon.reconnect_websocket`, `evon.set_home_state`,
  `evon.set_season_mode`, `evon.all_lights_off`, `evon.all_blinds_open`,
  `evon.all_blinds_close`.
- WebSocket connection status binary sensor (diagnostic); device triggers for doorbell
  ring and door open events; reduced poll interval while WebSocket is connected; entity
  categories.

### Fixed

- Climate presets over WebSocket use `SetValue ModeSaved` (2/3/4 heating, 5/6/7 cooling)
  instead of `CallMethod WriteDayMode` / `WriteNightMode` / `WriteFreezeMode`, which the
  controller acknowledged but ignored. (Reversed again in 1.16.0: the `CallMethod` calls
  are sent fire-and-forget because the controller sends no `MethodReturn` for them, and
  `SetValue ModeSaved` only updates the displayed number.)

## [1.14.0] - 2026-02-01

### Added

- **WebSocket device control** for lights, blinds and climate: instant response instead of
  waiting for the next poll cycle. Falls back to HTTP when WebSocket is unavailable.
- Security doors and intercoms with doorbell events, light and blind groups, RGBW colour
  temperature (untested), climate humidity display.

## [1.13.0] - 2026-01-31

### Added

- WebSocket support for real-time state updates (enabled by default), with reduced
  polling while connected.

## [1.12.0] - 2026-01-30

### Added

- Remote access through the `my.evon-smarthome.com` relay; the reconfigure flow switches
  between local and remote connections.

### Changed

- Security: explicit SSL context with connection limits, header redaction, token TTL with
  auto-refresh, comprehensive input validation, Engine ID redaction in diagnostics.

## [1.11.0] - 2026-01-29

### Added

- Scenes as button entities.
- Smart meter current sensors (L1/L2/L3), frequency sensor, feed-in energy sensor.

## [1.10.2] - 2026-01-29

### Fixed

- Data caching prevents entities from becoming unavailable during transient API failures.

## [1.10.1] - 2026-01-28

### Fixed

- Bathroom radiators show the remaining time optimistically.
- The smart meter's rolling 24-hour energy value is no longer offered as a daily total;
  it could decrease during the day and produced negative values in the Energy Dashboard.

## [1.10.0] - 2026-01-24

### Added

- Non-dimmable lights option.
- Home Assistant Repairs integration: connection failure alerts, stale entity
  notifications, config migration warnings.
- Hub device hierarchy.

### Changed

- Home state names use Home Assistant's translation system (German and English).
- Home Assistant 2025.12.0 compatibility (`via_device` warnings fixed). Config entry
  version 2 with migration.

## [1.9.0] - 2026-01-17

### Added

- Season Mode select for global heating/cooling (`Base.ehThermostat.IsCool`).
- Climate activity display (heating / cooling / idle).

### Fixed

- Climate presets map to the season-specific values (2 to 4 for heating, 5 to 7 for
  cooling).

## [1.8.2] - 2026-01-16

No GitHub release was published for this tag.

### Fixed

- Blind optimistic state for group actions; clicking a group button twice to stop works.
- Blind tilt open/close convention matches the Evon app (0 = open, 100 = closed); the
  hardware quirk (tilt orientation depends on the last movement direction) is documented
  in `docs/BLIND_TILT_BEHAVIOR.md` (bumped to 1.8.1 without a tag).

## [1.8.0] - 2026-01-16

### Changed

- Optimistic updates for all controllable entities.
- Climate presets renamed to Home Assistant's built-in names (`eco`, `away`) for better
  icons.

## [1.7.4] - 2026-01-16

### Fixed

- Optimistic target temperature when changing presets.

## [1.7.3] - 2026-01-16

### Fixed

- Optimistic preset mode to prevent UI flicker.

## [1.7.2] - 2026-01-15

### Fixed

- Climate preset detection for Thermostat devices (`MainState` fallback).

## [1.7.1] - 2026-01-15

### Fixed

- Climate preset detection uses `ModeSaved`; cooling/heating mode display added.

## [1.7.0] - 2026-01-15

### Added

- Bathroom radiator support with timer. MCP tools and resource for radiators.

## [1.6.0] - 2026-01-15

### Added

- Automatic cleanup of stale entities on reload.

## [1.5.2] - 2026-01-15

### Fixed

- Config flow updated to the modern Home Assistant config-flow API (`ConfigFlowResult`,
  `async_update_reload_and_abort()`, no `OptionsFlow.__init__()`), completing the 1.5.1
  fix.

## [1.5.1] - 2026-01-15

### Fixed

- Reconfigure flow 500 error: `async_step_reconfigure()` uses `_get_reconfigure_entry()`
  instead of the deprecated `async_get_entry(self.context["entry_id"])` pattern.

## [1.5.0] - 2026-01-15

### Added

- Home State selector. MCP tools and resource for home states.

## [1.4.1] - 2026-01-15

### Removed

- Non-functional button event entities (re-implemented in 1.19.0).

## [1.4.0] - 2026-01-15

### Added

- Event entities for physical buttons (removed again in 1.4.1).

## [1.3.3] - 2026-01-15

### Fixed

- Blind control uses `Open` / `Close` instead of the nonexistent `MoveUp` / `MoveDown`.

## [1.3.2] - 2026-01-15

### Added

- Logbook integration for switch click events.

## [1.3.1] - 2026-01-15

### Changed

- Entity categories, availability detection, `HomeAssistantError` exceptions,
  `EntityDescription` refactoring.

## [1.3.0] - 2026-01-15

### Added

- Smart meter, air quality and valve sensors; diagnostics support.
- German translations (bumped to 1.2.1 without a tag).

## [1.2.0] - 2026-01-15

### Added

- Optional area sync (Evon rooms to Home Assistant areas).

## [1.1.5] - 2026-01-15

### Fixed

- `AbortFlow` handling ("Unexpected error" when already configured).

## [1.1.4] - 2026-01-15

### Fixed

- API client error handling (JSON decode, unexpected errors).

## [1.1.3] - 2026-01-15

### Fixed

- Config flow "Unexpected error" (missing `strings.json`, auth error handling).

## [1.1.2] - 2026-01-15

### Fixed

- Switch detection (class name `SmartCOM.Switch`).

## [1.1.1] - 2026-01-15

### Changed

- Documentation and branding updates, HACS buttons.

## [1.1.0] - 2026-01-15

### Added

- Sensors, switches, options flow, reconfigure flow, MCP resources and scenes.

## [1.0.0] - 2026-01-15

### Added

- Initial release with lights, blinds and climate support.

[Unreleased]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.23.0...HEAD
[1.23.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.22.1...v1.23.0
[1.22.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.22.0...v1.22.1
[1.22.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.21.0...v1.22.0
[1.21.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.20.0...v1.21.0
[1.20.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.19.2...v1.20.0
[1.19.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.19.1...v1.19.2
[1.19.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.19.0...v1.19.1
[1.19.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.18.0...v1.19.0
[1.18.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.17.1...v1.18.0
[1.17.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.17.0...v1.17.1
[1.17.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.16.0...v1.17.0
[1.16.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.15.0...v1.16.0
[1.15.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.14.3...v1.15.0
[1.14.3]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.14.2...v1.14.3
[1.14.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.14.1...v1.14.2
[1.14.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.14.0...v1.14.1
[1.14.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.13.0...v1.14.0
[1.13.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.10.2...v1.11.0
[1.10.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.10.1...v1.10.2
[1.10.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.10.0...v1.10.1
[1.10.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.8.2...v1.9.0
[1.8.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.8.0...v1.8.2
[1.8.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.7.4...v1.8.0
[1.7.4]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.7.3...v1.7.4
[1.7.3]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.7.2...v1.7.3
[1.7.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.7.1...v1.7.2
[1.7.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.5.2...v1.6.0
[1.5.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.3.3...v1.4.0
[1.3.3]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.3.2...v1.3.3
[1.3.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.1.5...v1.2.0
[1.1.5]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.1.4...v1.1.5
[1.1.4]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/releases/tag/v1.0.0
