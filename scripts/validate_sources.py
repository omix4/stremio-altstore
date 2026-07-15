#!/usr/bin/env python3
"""Validate source safety and legacy/modern compatibility invariants."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from source_compat import CURRENT_FIELD_MAP, newest_version, version_key

REPO = Path(__file__).resolve().parent.parent
SOURCES = {
    "stremio-ios.json": {
        "source_url": "https://repo.omix4.one/stremio-ios.json",
        "platform": "ios",
    },
    "stremio-tvos.json": {
        "source_url": "https://repo.omix4.one/stremio-tvos.json",
        "platform": "tvos",
    },
}
EXPECTED_BUNDLES = {"com.stremio.pal", "com.stremio.ios"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URL_FIELDS = {"sourceURL", "website", "iconURL", "headerURL", "downloadURL"}


def _validate_https(value: object, context: str, errors: list[str]) -> None:
    if not isinstance(value, str) or urlparse(value).scheme != "https":
        errors.append(f"{context}: URL must use HTTPS")


def _validate_all_urls(value: object, context: str, errors: list[str]) -> None:
    """Recursively reject non-HTTPS values in every URL-shaped field."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_context = f"{context}.{key}"
            if key in URL_FIELDS or key.lower().endswith("url"):
                _validate_https(child, child_context, errors)
            _validate_all_urls(child, child_context, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_all_urls(child, f"{context}[{index}]", errors)


def validate_source(data: object, filename: str) -> list[str]:
    """Return all validation errors for one decoded source document."""
    errors: list[str] = []
    config = SOURCES.get(filename)
    if config is None:
        return [f"{filename}: no validation policy configured"]
    if not isinstance(data, dict):
        return [f"{filename}: source root must be an object"]

    if data.get("sourceURL") != config["source_url"]:
        errors.append(f"{filename}.sourceURL: expected {config['source_url']}")
    _validate_all_urls(data, filename, errors)

    apps = data.get("apps")
    if not isinstance(apps, list):
        return errors + [f"{filename}.apps: must be an array"]

    bundles = [app.get("bundleIdentifier") for app in apps if isinstance(app, dict)]
    if set(bundles) != EXPECTED_BUNDLES or len(bundles) != len(EXPECTED_BUNDLES):
        errors.append(
            f"{filename}.apps: expected exactly bundle IDs {sorted(EXPECTED_BUNDLES)}"
        )

    for index, app in enumerate(apps):
        context = f"{filename}.apps[{index}]"
        if not isinstance(app, dict):
            errors.append(f"{context}: must be an object")
            continue
        versions = app.get("versions")
        if not isinstance(versions, list) or not versions:
            errors.append(f"{context}.versions: must be a non-empty array")
            continue
        try:
            keys = [version_key(version) for version in versions]
            latest = newest_version(app)
        except (AttributeError, TypeError, ValueError) as exc:
            errors.append(f"{context}.versions: {exc}")
            continue
        if keys != sorted(keys, reverse=True):
            errors.append(f"{context}.versions: must be sorted newest-first numerically")

        for app_field, version_field in CURRENT_FIELD_MAP.items():
            if app.get(app_field) != latest.get(version_field):
                errors.append(
                    f"{context}.{app_field}: must mirror newest versions[].{version_field}"
                )

        for vindex, version in enumerate(versions):
            vcontext = f"{context}.versions[{vindex}]"
            if not isinstance(version, dict):
                errors.append(f"{vcontext}: must be an object")
                continue
            url = version.get("downloadURL")
            parsed = urlparse(url) if isinstance(url, str) else None
            if parsed and parsed.hostname != "dl.strem.io":
                errors.append(f"{vcontext}.downloadURL: host must be dl.strem.io")
            expected_path = f"/{config['platform']}/"
            if parsed and expected_path not in parsed.path:
                errors.append(
                    f"{vcontext}.downloadURL: path must identify {config['platform']}"
                )
            digest = version.get("sha256")
            if digest is not None and (
                not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)
            ):
                errors.append(f"{vcontext}.sha256: must be 64 lowercase hex characters")

    return errors


def validate_file(path: Path) -> list[str]:
    """Load and validate one source file, returning parse or schema errors."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"{path.name}: cannot parse source: {exc}"]
    return validate_source(data, path.name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", help="Source files (defaults to both canonical files)")
    args = ap.parse_args()
    paths = [Path(value) for value in args.files] if args.files else [REPO / f for f in SOURCES]
    errors = [error for path in paths for error in validate_file(path)]
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(f"[OK] Validated {len(paths)} source file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
