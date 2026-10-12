# Security Policy

## Supported versions

Only the latest release receives fixes. Please update through HACS (or by replacing
`custom_components/evon`) before reporting; older versions are not patched.

## Reporting a vulnerability

Do not open a public issue for a security problem. Use GitHub's private reporting
instead: **Security → Report a vulnerability** on this repository
(<https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/security/advisories/new>).

Please include:

- the integration version (`version` in `custom_components/evon/manifest.json`, or as
  shown in HACS) and the Home Assistant version;
- whether the controller is reached locally or through the remote relay;
- what an attacker can do and from where (local network, the Home Assistant port, the
  relay);
- steps to reproduce, or the code path if you found it by reading the source.

Redact your Engine ID, credentials and tokens from logs and screenshots.

## What to expect

This is a maintainer-run project without a security team. Reports are handled on a
best-effort basis: you should hear back within a few days, a confirmed problem is fixed in
the next release, and the advisory is published together with it. Please keep the report
private until then.

## Scope notes

- Camera recordings are served only through an authenticated Home Assistant endpoint
  (`/evon/recordings/{filename}`, `custom_components/evon/recordings_view.py`,
  `requires_auth = True`); anonymous requests get 401. Releases before 1.22.0 served them
  from an unauthenticated static path.
- Credentials are sent only to the Evon controller on your local network or, when remote
  access is configured, to the relay `https://my.evon-smarthome.com` (`EVON_REMOTE_HOST`
  in `custom_components/evon/const.py`). The password is hashed before it is sent
  (Base64 of SHA-512 over username + password). The integration contacts no other host.
