# Stremio — Unofficial AltStore Source

[![Update source](https://github.com/omix4/stremio-altstore/actions/workflows/update.yml/badge.svg)](https://github.com/omix4/stremio-altstore/actions/workflows/update.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stremio iOS versions](https://img.shields.io/badge/iOS-14%20versions-7055D9)](stremio-ios.json)
[![Stremio tvOS versions](https://img.shields.io/badge/tvOS-7%20versions-7055D9)](stremio-tvos.json)

An **unofficial** AltStore-format source collection for Stremio iOS and tvOS, compatible with signing apps that consume AltStore-style **plain IPA** sources — FlareStore, Feather, SideStore, AltStore Classic, ESign, Scarlet, KSign, and others. Stremio's official source at [`dl.strem.io/apple/altstore/source.json`](https://dl.strem.io/apple/altstore/source.json) cannot be parsed by most third-party signing apps because it uses Apple's encrypted App Store Connect marketplace format — this repo publishes standard source JSON that points to Stremio's plain IPA artifacts.

## Table of contents

- [Why does this repo exist?](#why-does-this-repo-exist)
- [Compatible signing apps](#compatible-signing-apps)
- [Quick start](#quick-start)
- [Self-host your own copy](#self-host-your-own-copy)
- [Available versions](#available-versions)
- [Automatic updates](#automatic-updates)
- [Manual updates](#manual-updates)
- [Architecture](#architecture)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License and attribution](#license-and-attribution)

---

## Why does this repo exist?

Starting in June 2026, Stremio moved iOS distribution entirely to Apple's **App Store Connect marketplace** format. This format:

1. Packages IPAs as encrypted variant chunks
2. Distributes a `manifest.json` metadata file
3. Grants the decryption key only to AltStore PAL

Most third-party signing apps (FlareStore, Feather, SideStore, ESign, Scarlet, etc.) cannot use that encrypted distribution, so importing the official source results in "no apps", "invalid format", or "failed to download" errors.

However, Stremio keeps the plain IPA files **publicly available on the same CDN**:

```
https://dl.strem.io/apple/{X.Y.Z}b{buildN}/{ios|tvos}/stremio_{Platform}.ipa
```

This repo discovers those IPAs and writes them into standard AltStore-format JSON sources.

> 📜 Related discussions:
> - [Stremio #2384 — Publish Stremio iOS on AltStore as an official source](https://github.com/Stremio/stremio-bugs/issues/2384)
> - [Stremio blog — Sideloadable IPA Release](https://blog.stremio.com/stremio-fully-featured-sideloadable-ipa-release-for-ios-ipados-apple-tv-tvos/)
> - [@blksmr — original unofficial source](https://github.com/blksmr/altstore-stremio)

---

## Compatible signing apps

Any signing app that consumes the standard AltStore source format can use this repo. Tested or known-compatible apps include:

- **[Feather](https://github.com/claration/Feather)** — open-source on-device signer
- **[SideStore](https://sidestore.io)** — fully compatible with AltStore sources
- **[AltStore Classic](https://altstore.io)** — the original desktop-paired signer (requires AltServer on a Mac/PC)
- **[FlareStore](https://flarestore.app)** — repository browser and web signer
- **[ESign](https://github.com/jakepoz/esign)** — popular on-device signer
- **[Scarlet](https://usescarlet.com)** — on-device IPA installer

AltStore PAL uses Apple's notarized ADP/marketplace format rather than plain IPA downloads, so use Stremio's official PAL source there. Sideloadly can install an IPA downloaded from the source, but it does not consume the repository URL itself.

If your signing app supports adding a source by URL pointing to an `apps.json`-style document, it will work. If you find an app that does not work, please open an issue.

---

## Quick start

**No fork required.** This source is already hosted and auto-updated every 6 hours. Just add it to your signing app.

### Add the URL manually

Works with signing apps that accept AltStore-style plain-IPA sources (FlareStore, Feather, SideStore, AltStore Classic, ESign, Scarlet, KSign…). Paste the URL into the app's **Sources** / **Repositories** section:

| Platform | Source URL |
|---|---|
| iOS / iPadOS | `https://repo.omix4.one/stremio-ios.json` |
| tvOS | `https://repo.omix4.one/stremio-tvos.json` |

Once added, Stremio appears in the app's source list. Pick a version and tap **Get** (or the equivalent) to download and sign.

### Alternative: raw GitHub URL (no Pages)

`sourceURL` also works with `raw.githubusercontent.com`:

```
https://raw.githubusercontent.com/omix4/stremio-altstore/main/stremio-ios.json
https://raw.githubusercontent.com/omix4/stremio-altstore/main/stremio-tvos.json
```

Some signing apps require the `Content-Type: application/json` header, which the hosted source guarantees; raw URLs occasionally delay that header — prefer the `repo.omix4.one` URLs above.

---

## Self-host your own copy

Prefer to run your own source (own URL, own update schedule)? Fork and host it in a couple of minutes:

1. **Fork** this repository.
2. Enable Pages: **Settings → Pages → Source: Deploy from a branch → Branch: `main` / `(root)`**. After a few minutes your sources are live at `https://<your-github-username>.github.io/stremio-altstore/stremio-{ios,tvos}.json`.
3. Point `sourceURL` at your fork:
   ```bash
   python3 stremio-updater.py \
     --source-url-ios  "https://<your-github-username>.github.io/stremio-altstore/stremio-ios.json" \
     --source-url-tvos "https://<your-github-username>.github.io/stremio-altstore/stremio-tvos.json"
   ```
4. Commit the change. The included GitHub Actions workflow keeps your fork updated every 6 hours.

---

## Available versions

<!-- BEGIN:AVAILABLE_VERSIONS -->

### iOS / iPadOS — `stremio-ios.json`

#### Stremio (PAL, full-featured) — `com.stremio.pal`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 2.0.6 | 21 | 2026-07-22 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.6b21/ios/stremio_iOS.ipa) |
| 2.0.5 | 20 | 2026-07-22 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.5b20/ios/stremio_iOS.ipa) |
| 2.0.4 | 19 | 2026-07-10 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.4b19/ios/stremio_iOS.ipa) |
| 2.0.3 | 18 | 2026-07-11 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.3b18/ios/stremio_iOS.ipa) |
| 2.0.2 | 17 | 2026-06-19 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.2b17/ios/stremio_iOS.ipa) |
| 2.0.1 | 16 | 2026-06-16 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.1b16/ios/stremio_iOS.ipa) |
| 2.0.1 | 15 | 2026-06-15 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.1b15/ios/stremio_iOS.ipa) |
| 2.0.0 | 14 | 2026-06-05 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.0b14/ios/stremio_iOS.ipa) |
| 2.0.0 | 13 | 2026-06-05 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.0b13/ios/stremio_iOS.ipa) |
| 2.0.0 | 11 | 2026-05-30 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.0b11/ios/stremio_iOS.ipa) |

#### Stremio Lite (legacy) — `com.stremio.ios`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 1.3.6 | 7 | 2026-01-31 | 75 MB | [IPA](https://dl.strem.io/apple/1.3.6b7/ios/stremio_iOS.ipa) |

#### Stremio Legacy (legacy archive) — `com.stremio.one`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 1.3.2 | 2 | 2025-11-19 | 55 MB | [IPA](https://dl.strem.io/apple/1.3.2b2/ios/stremio_iOS.ipa) |
| 1.3.0 | 1 | 2025-10-03 | 54 MB | [IPA](https://dl.strem.io/apple/1.3.0b1/ios/stremio_iOS.ipa) |
| 1.2.0 | 10 | 2025-07-08 | 68 MB | [IPA](https://dl.strem.io/apple/1.2.0b10/ios/stremio_iOS.ipa) |

### tvOS — `stremio-tvos.json`

#### Stremio (PAL, full-featured) — `com.stremio.pal`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 2.0.6 | 21 | 2026-07-22 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.6b21/tvos/stremio_tvOS.ipa) |
| 2.0.5 | 20 | 2026-07-22 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.5b20/tvos/stremio_tvOS.ipa) |
| 2.0.3 | 18 | 2026-07-11 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.3b18/tvos/stremio_tvOS.ipa) |
| 2.0.2 | 17 | 2026-06-19 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.2b17/tvos/stremio_tvOS.ipa) |
| 2.0.1 | 16 | 2026-06-16 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.1b16/tvos/stremio_tvOS.ipa) |
| 2.0.1 | 15 | 2026-06-15 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.1b15/tvos/stremio_tvOS.ipa) |

#### Stremio Lite (legacy) — `com.stremio.ios`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 1.3.6 | 7 | 2026-01-31 | 73 MB | [IPA](https://dl.strem.io/apple/1.3.6b7/tvos/stremio_tvOS.ipa) |

<!-- END:AVAILABLE_VERSIONS -->

> 🤖 The tables above are auto-generated from the JSON sources by `scripts/render_readme.py` on every update — do not edit them by hand.

> 📦 Every version was verified against the IPA's Info.plist (downloaded via HTTP Range, < 5 KB each). Bundle identifiers, version strings, and `MinimumOSVersion` values were read directly from the IPAs.

> 🗃️ **Legacy archive:** Historical CDN candidates were rechecked before publication. Only the three additional iOS builds shown under `com.stremio.one` were still downloadable and internally verifiable; the other reported historical iOS/tvOS URLs returned 404 and are intentionally omitted.

---

## Automatic updates

The repo includes a GitHub Actions workflow that runs `stremio-updater.py` every 6 hours, discovers new Stremio versions, updates the JSON files, and auto-commits. With GitHub Pages enabled, new versions appear in your signing app within minutes. Discovery uses a small pattern-based search frontier against the plain IPA CDN, plus Stremio's official AltStore PAL source as an optional metadata and exact-version hint after Apple notarization completes.

Each run also, in the same job:

- **Backfills integrity hashes** — `scripts/add_hashes.py` computes the `sha256` of a few IPAs per run (newest first, budget-limited so it never risks the job's time limit), so every version eventually carries a hash that signing apps can verify the download against.
- **Regenerates the version tables** in this README from the JSON.

A separate **CDN health canary** (`scripts/check_cdn.py`) runs on the same schedule. Because the updater exits successfully whether it finds new versions or finds nothing, a broken CDN (a changed URL scheme, an outage, or a pulled build) would otherwise be invisible. The canary HEAD-checks every listed IPA and **opens a GitHub issue** (deduplicated — one at a time) if the source may be serving a dead download.

To enable the workflow: **Actions → Update Stremio source → Enable workflow**.

To trigger manually: **Actions → Update Stremio source → Run workflow**.

Configuration lives in `.github/workflows/update.yml`.

---

## Manual updates

```bash
# Clone the repo
git clone https://github.com/omix4/stremio-altstore.git
cd stremio-altstore

# Virtual environment (optional but recommended)
python3 -m venv .venv && source .venv/bin/activate

# Dry run — see what would change without writing files
python3 stremio-updater.py --dry-run --verbose

# Real update — write changes to JSON files
python3 stremio-updater.py

# Parse Info.plist for unknown IPAs to verify bundle IDs (slower)
python3 stremio-updater.py --info-plist

# Only iOS (or only tvOS)
python3 stremio-updater.py --platform ios
python3 stremio-updater.py --platform tvos

# Update sourceURL fields
python3 stremio-updater.py \
  --source-url-ios  "https://<your-github-username>.github.io/stremio-altstore/stremio-ios.json" \
  --source-url-tvos "https://<your-github-username>.github.io/stremio-altstore/stremio-tvos.json"

# Commit and push
git add stremio-ios.json stremio-tvos.json
git commit -m "chore: update Stremio source"
git push
```

Shorter aliases via `make`:

```bash
make help         # List all targets
make dry-run      # Dry run
make update       # Real update
make verify       # Update with Info.plist verification
make set-urls     # Set sourceURL fields interactively
```

---

## Architecture

```
stremio-altstore/
├── README.md                   ← this file
├── LICENSE                     ← MIT
├── CHANGELOG.md                ← version history
├── CONTRIBUTING.md             ← contribution guide
├── SECURITY.md                 ← security policy
├── Makefile                    ← shortcut commands
├── .gitignore                  ← Python / macOS / IDE
├── stremio-ios.json            ← main source (iOS / iPadOS)
├── stremio-tvos.json           ← main source (tvOS)
├── stremio-updater.py          ← CDN scanner + JSON updater
├── ipa_plist.py                ← shared HTTP-Range IPA Info.plist parser
├── assets/
│   └── stremio-icon.png         ← self-hosted source and app icon
├── .github/
│   ├── workflows/
│   │   └── update.yml          ← auto-update every 6 hours + CDN canary
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.yml
│       ├── feature_request.yml
│       └── source_broken.yml
└── scripts/
    ├── verify_bundle_ids.py    ← standalone IPA Info.plist verifier
    ├── render_readme.py        ← regenerates the version tables above
    ├── add_hashes.py           ← backfills sha256 integrity hashes (budgeted)
    └── check_cdn.py            ← CDN health canary (opens an issue if broken)
```

### Why two JSON files?

Stremio uses the **same bundle identifier** on both iOS and tvOS: `com.stremio.pal`. Most signing apps do not allow two apps with the same `bundleIdentifier` inside one source (signing/conflict reasons). That's why:

- `stremio-ios.json`  → iPhone / iPad (`com.stremio.pal`, `com.stremio.ios`, and the surviving `com.stremio.one` legacy archive)
- `stremio-tvos.json` → Apple TV (`com.stremio.pal` and `com.stremio.ios`, in separate sources — no conflict)

You can add both to your signing app; the appropriate one shows up per device type.

### How the updater works

1. **Candidate generation**: Builds independent PAL and Lite frontiers from the newest local version/build. It checks only the next three builds and plausible same-version, patch, minor, and PAL major transitions — at most 54 normal HEAD requests across both platforms.
2. **Official reconciliation**: Reads Stremio's official PAL source once as an optional hint. Exact version/build pairs and compatible release metadata are merged into the scan, but encrypted marketplace URLs, sizes, and permissions are never copied into this plain-IPA source.
3. **`scan_cdn`**: Probes the deduplicated `dl.strem.io/apple/{semver}b{build}/{ios|tvos}/...` candidates in parallel with a `ThreadPoolExecutor` (16 workers). Only HTTP 200 plain IPA artifacts are accepted.
4. **`get_main_app_info_plist`**: Fetches only the relevant chunks of each new IPA via HTTP `Range` requests and verifies its embedded version, build, and bundle identifier before publication.
5. **`process_platform`**: Adds verified releases or enriches earlier CDN discoveries with official patch notes, dates, and compatible metadata when they become available.

---

## Limitations

- **Unofficial** — Stremio does not support this source. It can change IPA URLs or shut down the CDN at any time.
- **Signature expiry** — Apps signed with a free Apple ID expire after **7 days**, with a paid developer account after **1 year**. You'll need to re-sign through your signing app.
- **Missing features** — Per Stremio's blog, some features (Apple Login, Handoff) don't work in sideloaded builds: *"these features cannot be available within sideloadable apps"*.
- **CDN dependency** — If Stremio changes its `dl.strem.io` infrastructure, this repo breaks. Run `updater.py --dry-run` periodically to verify.

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Especially helpful:

- 🆕 **Reporting new versions** — open an Issue or PR if the updater missed one
- 🐛 **Bug fixes** — particularly parse errors and edge cases
- 📚 **Documentation** — README translations, clarifications, examples
- 🧪 **Testing** — compatibility with different signing apps
- 🆕 **Adding new signing app support** — if a signing app has trouble parsing our JSON, file an Issue with the parsing error message

For security issues please see [SECURITY.md](SECURITY.md).

---

## License and attribution

This repository is licensed under the [MIT License](LICENSE).

- **Stremio** is a trademark of SmartCode OOD. This repo is not affiliated with, endorsed by, or sponsored by Stremio or SmartCode OOD.
- **AltStore** and the source format are defined by [AltStore](https://altstore.io).
- **Feather** is an open-source project by [@claration](https://github.com/claration/Feather).
- Original unofficial source inspiration: [@blksmr/altstore-stremio](https://github.com/blksmr/altstore-stremio).

---

<p align="center">
  <sub>This source is maintained by the community, with love 🍿</sub>
</p>
