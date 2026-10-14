# Intercom Audio & Doorbell Notifications

How to get a **doorbell push notification** (with a snapshot and a one-tap door
opener) and **two-way audio** with a 2N door station **inside Home Assistant**.

This is an optional, self-hosted setup that sits *alongside* the Evon integration.
The integration itself only contributes two things here: the **door-opener button**
(`EvonIntercomDoorButton`, see [AGENTS.md → Physical Buttons / door opener] and
[WEBSOCKET_API.md → Door opener]) and the **Talk button** on the camera card
(`www/evon-camera-recording-card.js`, config key `sip_extension`). Everything else
is Home Assistant add-ons and config, not integration code, so none of it is
installed automatically.

> **Status:** verified working on one deployment (October 2026): doorbell
> notifications, outbound "Talk" to the door, and two-way audio both directions.
> The in-card "Answer" state for an incoming call is new and still being verified.

## Why it is not trivial

- Evon exposes the door call over its **cloud SIP** service (`sip.evon-smarthome.at`),
  not on the LAN. The 2N device itself is usually unreachable from Home Assistant.
- Evon's SIP server answers **UDP only** (no WebSocket/TLS), so a browser SIP card
  cannot talk to it directly. A small PBX (the Asterisk add-on) bridges UDP ↔ the
  browser's WebRTC.
- Browsers grant microphone access only in a **secure context (HTTPS)**. A plain
  `http://<ip>:8123` instance cannot do two-way audio. You need HTTPS in front of HA.

## Architecture

```
2N door ──(Evon cloud SIP, UDP 5060)──► Asterisk add-on ──(WebSocket/ingress)──► SIP Core card
 door1_xxxxxx        registers as:          on Home Assistant                     in the dashboard
                     user1_xxxxxx           pjsip trunk + dialplan                (phones / tablet)
                                                   ▲
                                            Tailscale Serve provides the trusted
                                            HTTPS URL the devices connect through
```

The door-opener uses the Evon API (the integration's button), **not** DTMF, so it
works whether or not a call is up.

## Requirements

| Need | Why |
|------|-----|
| Evon user SIP credentials | `GlobalSipUsername` / `GlobalSipPassword` / `GlobalSipServer` on a `System.User` object (read them in the Evon app's user settings). The door's SIP user is on the intercom object's `SIPUser`. |
| **Asterisk add-on** (`hassio-addons`, `TECH7Fox/asterisk-hass-addons`) | The PBX that registers to Evon and bridges audio. |
| **SIP Core** integration + card (`TECH7Fox/sip-hass-card`, built, dropped into `custom_components/sip_core`) | The browser WebRTC client (`window.sipCore`) and the call popup. |
| **HTTPS** to Home Assistant | Microphone needs a secure context. The easiest self-hosted route is the **Tailscale add-on** with `share_homeassistant: serve` (free, trusted cert, also replaces a VPN). Nabu Casa works too. |
| A doorbell `event` entity + a door-opener `button` | Provided by the Evon integration for 2N intercoms. |

## Setup

### 1. Asterisk add-on (the PBX)

1. Install the **Asterisk** add-on and set two internal secrets in its config:
   `ami_password` and `auto_add_secret` (any strong values; you will reuse them).
2. Put three files in `/addon_configs/<asterisk-slug>/asterisk/custom/` (create the
   `custom/` folder next to the generated `default/`):
   - `pjsip_custom.conf` — the **trunk** to Evon (registration + endpoint + identify).
     The pulse length / SIP password is yours; see the template below.
   - `extensions.conf` — the **dialplan**: an outbound route to the door
     (`exten => 8001 → Dial(PJSIP/<door-sip-user>@evon_endpoint)`) and an inbound
     context that rings the handset extensions **without auto-answering** (so the
     2N hardware keeps ringing).
   - `manager.conf` — a copy of the generated one with the **AMI permit list**
     widened to the HA container/host network, so the SIP Core integration can log in.
3. Restart the add-on. Confirm in its log: `Outbound registration ... successful`
   and a `200` from `sip.evon-smarthome.at`.

> **Gotcha:** a new `custom/extensions.conf` route (e.g. `8001`) only takes effect
> after an add-on **restart** — reloading is not enough. If the Talk/outbound call
> drops with `Specified endpoint '8001' was not found`, the route is not loaded.

### 2. SIP Core integration + card

1. Build the card/integration from `TECH7Fox/sip-hass-card` (webpack → the repo's
   `custom_components/sip_core/www/sip_core.js`) and copy `custom_components/sip_core`
   into your HA config. Restart HA, then add the **SIP Core** integration.
2. In its options, paste a `sip_config` object mapping your HA users to the
   auto-created extensions (numbered from 100), with the password = `auto_add_secret`,
   a `popup_config` with an "open door" service-call button, and the door camera.
3. **AMI connection** (if asked): host = the HA host/gateway (e.g. `172.30.32.1`),
   port `5038`, user `admin`, password = `ami_password`. If it says *Unauthorized*,
   widen `permit` in `custom/manager.conf` to include the source IP from the add-on
   log (`Connect attempt from X unable to authenticate`).

### 3. HTTPS via Tailscale (so the mic works)

1. Install the **Tailscale** add-on, start it, open the login URL from its log,
   and authorize HA onto your tailnet. Disable key expiry on the HA node.
2. In the Tailscale admin console: enable **MagicDNS** and **HTTPS certificates**.
3. Add-on config: `share_homeassistant: serve` (tailnet-only; `funnel` is public).
4. In HA, **Settings → System → Network → HTTP server**, enable *Trust
   X-Forwarded-For* and add `127.0.0.1` and `::1` to *Trusted proxies*, then confirm.
   This lives in `.storage`, **not** `configuration.yaml` — a YAML `http:` block is
   ignored once HA has migrated HTTP config to the UI (`Using stable HTTP config`).
5. Restart the Tailscale add-on. Your HA is now at
   `https://<host>.<tailnet>.ts.net` with a trusted cert. Point the companion app
   at that URL and install Tailscale on each phone.

### 4. The card button + notifications

- Add `sip_extension: "8001"` to the Evon camera card (`custom:evon-camera-recording-card`)
  so the **Talk** button appears next to "Open door". It answers an incoming call,
  hangs up an active one, or dials the door when idle, via `window.sipCore`.
- Two automations (see your automations, documented there):
  - **doorbell → notification:** on the intercom's `event.*_doorbell`, send a
    high-priority notification with a fresh camera snapshot, a `clickAction` that
    deep-links to the door popup (e.g. `/dashboard-home#door-camera`), and an
    `EVON_OPEN_DOOR` action button.
  - **action → open door:** on `mobile_app_notification_action == EVON_OPEN_DOOR`,
    press the door-opener button.

## Config templates

**`pjsip_custom.conf`** (replace `<USER>`, `<PW>`, `<DOOR>`):

```ini
[evon_reg]
type=registration
transport=transport-udp
outbound_auth=evon_auth
server_uri=sip:sip.evon-smarthome.at:5060
client_uri=sip:<USER>@sip.evon-smarthome.at
contact_user=<USER>
retry_interval=60
forbidden_retry_interval=300
expiration=600

[evon_auth]
type=auth
auth_type=userpass
username=<USER>
password=<PW>

[evon_aor]
type=aor
contact=sip:sip.evon-smarthome.at:5060
qualify_frequency=60

[evon_endpoint]
type=endpoint
transport=transport-udp
context=from-evon
disallow=all
allow=alaw,ulaw
outbound_auth=evon_auth
aors=evon_aor
from_user=<USER>
from_domain=sip.evon-smarthome.at
direct_media=no

[evon_identify]
type=identify
endpoint=evon_endpoint
match=sip.evon-smarthome.at
```

**`extensions.conf`** (door route + inbound ring; `<DOOR>` is the door SIP user):

```ini
[default]
include => parkedcalls
exten => 8001,1,NoOp(Calling door station via Evon trunk)
 same => n,Dial(PJSIP/<DOOR>@evon_endpoint,30)
 same => n,Hangup()
exten => _X!,1,Dial(${PJSIP_DIAL_CONTACTS(${EXTEN})})

[from-evon]
exten => h,1,Hangup()
exten => i,1,Hangup()
exten => s,1,Goto(evon-ring,s,1)
exten => <USER>,1,Goto(evon-ring,s,1)
exten => _X!,1,Goto(evon-ring,s,1)
exten => _[a-z0-9]!,1,Goto(evon-ring,s,1)

[evon-ring]
exten => s,1,NoOp(Door intercom -> ring handsets)
 same => n,Dial(PJSIP/100&PJSIP/101&PJSIP/102,45,rtT)
 same => n,Hangup()
```

(Keep the add-on's generated `[general]`/`[parkedcallstimeout]` sections; `custom/`
files replace the default of the same name, so copy the default and add to it.)

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Outbound call drops instantly, log shows `Specified endpoint '8001' was not found` | The `8001` route is not in the loaded dialplan — the `custom/extensions.conf` is missing it or the add-on was not **restarted** after the edit. |
| SIP Core AMI says *Unauthorized* | `custom/manager.conf` permit list does not include the source IP in `Connect attempt from X unable to authenticate`. Widen `permit=`. |
| No microphone / call has no audio | HA not reached over **HTTPS**. Use the Tailscale `ts.net` URL, not `http://<ip>:8123`. |
| Trust-proxy error, `A request from a reverse proxy ... not set-up for reverse proxies` | Set *Trust X-Forwarded-For* + trusted proxies in **Settings → System → Network** (UI, not YAML). |
| Card changes do not show after deploy | HA frontend caches the module. Bump the Lovelace resource URL with `?v=<n>` (served with `cache_headers=False`, but the service worker still caches). |
| Registering the Asterisk trunk drops an Evon app | The trunk shares the household SIP identity (`UseStaticSIP`). Reopen the Evon app to re-register, or use a dedicated SIP sub-account. |

## Security note

Evon's API returns **secrets in cleartext** to any authenticated user, including the
2N device admin password, the SIP passwords, and the alarm code (via
`GET /api/instances/<id>`). Treat the SIP credentials you place in `pjsip_custom.conf`
accordingly, and keep add-on config out of version control (it is not tracked here).
