---
name: Bug report
about: Something does not work as documented
labels: bug
---

**Environment**

- Integration version (as shown in HACS, or `version` in `custom_components/evon/manifest.json`):
- Home Assistant version:
- Installation type (Home Assistant OS / Supervised / Container / Core venv):
- Connection: local IP or remote (`my.evon-smarthome.com`):
- Evon controller / software version, if known:

**Steps to reproduce**

1.
2.

**Expected behaviour**

**Actual behaviour**

**Relevant log lines**

Enable debug logging first: Settings → Devices & services → Evon Smart Home → Configure →
Debug Logging (API / WebSocket / Coordinator), reproduce the problem, then copy the lines
from Settings → System → Logs (maintainers with SSH access can use `./scripts/ha-logs.sh`).
Redact your Engine ID, username, password and tokens.

```
paste here
```
