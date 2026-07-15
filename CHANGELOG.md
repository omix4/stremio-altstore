# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-06-23

### Added
- `stremio-ios.json` — AltStore-format source for iOS / iPadOS
  - Stremio PAL (full-featured) — `com.stremio.pal`, 6 versions (2.0.0b11 → 2.0.2b17)
  - Stremio Lite (legacy) — `com.stremio.ios`, 1 version (1.3.6b7)
- `stremio-tvos.json` — Separate AltStore-format source for Apple TV
  - Stremio PAL — `com.stremio.pal`, 3 versions (2.0.1b15 → 2.0.2b17)
  - Stremio Lite — `com.stremio.ios`, 1 version (1.3.6b7)
- `stremio-updater.py` — `dl.strem.io` CDN scanner
  - Parallel HEAD requests (ThreadPoolExecutor, 16 workers)
  - HTTP Range-based IPA Info.plist extraction (XML + binary plist, via `plistlib`)
  - Main-app Info.plist filtering (excludes framework and appex entries)
  - Scans known + plausible upcoming semver/build combinations
- `.github/workflows/update.yml` — Auto-update every 6 hours
- `.github/ISSUE_TEMPLATE/` — Bug, feature, source-broken, and question templates
- `Makefile` — Shortcut commands (`make update`, `make dry-run`, etc.)
- `scripts/verify_bundle_ids.py` — Standalone IPA Info.plist verifier
- Bundle identifier, version, build, and `MinimumOSVersion` values verified against IPA Info.plist
- Compatibility with all signing apps that consume the standard AltStore source format (Feather, AltStore Classic, AltStore PAL, ESign, Scarlet, Sideloadly, and others)

### Notes
- Stremio's official `dl.strem.io/apple/altstore/source.json` source cannot be parsed by most third-party signing apps because it uses Apple's encrypted App Store Connect manifest format. This repo is an unofficial port that points to the plain IPAs available on the same CDN.
- Two separate JSON files are used because Stremio uses the same bundle identifier (`com.stremio.pal`) on both iOS and tvOS, and most signing apps do not allow two apps with the same `bundleIdentifier` inside one source.

[Unreleased]: https://github.com/omix4/stremio-altstore/compare/8099dadc70ee38337558f8dd5feec21827fba10a...HEAD
[1.0.0]: https://github.com/omix4/stremio-altstore/commit/8099dadc70ee38337558f8dd5feec21827fba10a
