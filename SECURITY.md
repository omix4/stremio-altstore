# Security Policy

## Supported versions

This repository is a **data/file collection** (JSON sources + Python scripts). "Version" here refers to JSON-tracked IPA references rather than software releases. Instead of a traditional "supported versions" list, follow [GitHub Releases](https://github.com/omix4/stremio-altstore/releases) for the freshness of IPA references.

| Component | Status |
|---|---|
| `stremio-ios.json` | ✅ Actively maintained |
| `stremio-tvos.json` | ✅ Actively maintained |
| `stremio-updater.py` | ✅ Actively maintained |
| Legacy IPA references | ⚠️ Available as long as Stremio keeps them on the CDN |

## Reporting a vulnerability

This repository does not execute code directly; it only collects data and produces JSON. However, if you discover a security issue or suspect something is wrong:

**Please DO NOT open a public Issue.** Instead:

1. Use **GitHub Security Advisories**:
   https://github.com/omix4/stremio-altstore/security/advisories/new

2. Or contact the maintainer directly via the email on their GitHub profile.

In your report, please include:

- Affected component (e.g. `stremio-updater.py`, `stremio-ios.json`)
- Description of the issue and its potential impact
- Reproduction steps (PoC if available)
- Suggested fix (if any)

**Response time:** initial response within 7 days, assessment within 30 days.

## Known security notes

### Signature expiry

IPAs in this source are distributed with **Stremio's official Apple Developer signature**. When re-signed via any signing app (Feather, AltStore, ESign, etc.):

- With a free Apple ID: expires after **7 days**
- With a paid developer account: expires after **1 year**

If you don't re-sign, the app stops launching. This is Apple's rule, not a repo issue.

### CDN security

`dl.strem.io` belongs to Stremio. This repo only uses **publicly accessible** URLs. If Stremio takes down the CDN or changes its structure, the repo breaks — open an Issue in that case.

### Third-party dependencies

This repository has **zero third-party Python dependencies**. It uses only the Python 3.8+ standard library. You will not find `requirements.txt` or `Pipfile` — that's intentional.

### SHA256 verification

The JSON files include SHA-256 hashes on nested version records. The automated updater
backfills hashes from the live `dl.strem.io` IPA files, and source validation rejects malformed
digests before publishing.

## Acknowledgements

Thank you to any researchers who report security issues responsibly.
