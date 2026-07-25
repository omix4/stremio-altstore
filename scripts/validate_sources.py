#!/usr/bin/env python3
"""Validate source safety and legacy/modern compatibility invariants."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from source_compat import CURRENT_FIELD_MAP, newest_version, version_key

REPO = Path(__file__).resolve().parent.parent
ICON_URL = "https://repo.omix4.one/assets/stremio-icon.png"
REPO_WEBSITE = "https://repo.omix4.one"
MAX_NEWS_ITEMS = 15
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCES = {
    "stremio-ios.json": {
        "source_url": "https://repo.omix4.one/stremio-ios.json",
        "platform": "ios",
        "bundles": {"com.stremio.pal", "com.stremio.ios", "com.stremio.one"},
        "required_bundles": {"com.stremio.pal"},
    },
    "stremio-tvos.json": {
        "source_url": "https://repo.omix4.one/stremio-tvos.json",
        "platform": "tvos",
        "bundles": {"com.stremio.pal", "com.stremio.ios"},
        "required_bundles": {"com.stremio.pal"},
    },
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URL_FIELDS = {"sourceURL", "website", "iconURL", "headerURL", "downloadURL"}
SOURCE_STRING_FIELDS = {"name"}
APP_STRING_FIELDS = {
    "name",
    "bundleIdentifier",
    "developerName",
    "localizedDescription",
    "iconURL",
}
LEGACY_APP_STRING_FIELDS = {"version", "versionDate", "downloadURL"}
VERSION_STRING_FIELDS = {"version", "buildVersion", "date", "downloadURL"}


def _require_nonempty_strings(
    value: dict, fields: set[str], context: str, errors: list[str]
) -> None:
    for field in sorted(fields):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append(f"{context}.{field}: must be a non-empty string")


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


def _is_mzstatic_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "mzstatic.com" or host.endswith(".mzstatic.com")
    )


def _validate_screenshot_entries(
    entries: object, context: str, errors: list[str]
) -> None:
    if not isinstance(entries, list) or len(entries) > 10:
        errors.append(f"{context}: must be an array of at most 10 screenshots")
        return
    for index, entry in enumerate(entries):
        item_context = f"{context}[{index}]"
        if isinstance(entry, str):
            if not _is_mzstatic_url(entry):
                errors.append(f"{item_context}: must be an HTTPS mzstatic.com URL")
            continue
        if not isinstance(entry, dict) or not set(entry).issubset(
            {"imageURL", "width", "height"}
        ):
            errors.append(f"{item_context}: invalid screenshot object")
            continue
        if not _is_mzstatic_url(entry.get("imageURL")):
            errors.append(f"{item_context}.imageURL: must be an HTTPS mzstatic.com URL")
        for dimension in ("width", "height"):
            if dimension in entry and (
                not isinstance(entry[dimension], int)
                or isinstance(entry[dimension], bool)
                or entry[dimension] <= 0
            ):
                errors.append(f"{item_context}.{dimension}: must be a positive integer")


def _validate_screenshots(value: object, context: str, errors: list[str]) -> None:
    if isinstance(value, list):
        _validate_screenshot_entries(value, context, errors)
        return
    if not isinstance(value, dict) or not value or not set(value).issubset(
        {"iphone", "ipad"}
    ):
        errors.append(f"{context}: must be an array or iPhone/iPad screenshot object")
        return
    for device, entries in value.items():
        _validate_screenshot_entries(entries, f"{context}.{device}", errors)


def _validate_news(data: dict, filename: str, bundles: set[str], errors: list[str]) -> None:
    news = data.get("news")
    if not isinstance(news, list):
        errors.append(f"{filename}.news: must be an array")
        return
    if len(news) > MAX_NEWS_ITEMS:
        errors.append(f"{filename}.news: must contain at most {MAX_NEWS_ITEMS} items")

    identifiers = []
    for index, item in enumerate(news):
        context = f"{filename}.news[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{context}: must be an object")
            continue
        _require_nonempty_strings(
            item, {"title", "identifier", "caption", "date"}, context, errors
        )
        identifier = item.get("identifier")
        if isinstance(identifier, str):
            identifiers.append(identifier)
        published = item.get("date")
        if not isinstance(published, str) or not DATE_RE.fullmatch(published):
            errors.append(f"{context}.date: must use YYYY-MM-DD")
        else:
            try:
                datetime.strptime(published, "%Y-%m-%d")
            except ValueError:
                errors.append(f"{context}.date: must be a real calendar date")
        if not isinstance(item.get("notify"), bool):
            errors.append(f"{context}.notify: must be a boolean")
        if item.get("appID") not in bundles:
            errors.append(f"{context}.appID: must identify an app in this source")
        tint = item.get("tintColor")
        if not isinstance(tint, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", tint):
            errors.append(f"{context}.tintColor: must be a six-digit hex color")

    if len(identifiers) != len(set(identifiers)):
        errors.append(f"{filename}.news: identifiers must be unique")
    sortable = [item for item in news if isinstance(item, dict)]
    expected = sorted(
        sortable,
        key=lambda item: (str(item.get("date", "")), str(item.get("identifier", ""))),
        reverse=True,
    )
    if sortable != expected:
        errors.append(f"{filename}.news: must be sorted newest-first")


def validate_source(data: object, filename: str) -> list[str]:
    """Return all validation errors for one decoded source document."""
    errors: list[str] = []
    config = SOURCES.get(filename)
    if config is None:
        return [f"{filename}: no validation policy configured"]
    if not isinstance(data, dict):
        return [f"{filename}: source root must be an object"]

    _require_nonempty_strings(data, SOURCE_STRING_FIELDS, filename, errors)
    if data.get("sourceURL") != config["source_url"]:
        errors.append(f"{filename}.sourceURL: expected {config['source_url']}")
    if data.get("iconURL") != ICON_URL:
        errors.append(f"{filename}.iconURL: expected {ICON_URL}")
    if data.get("headerURL") != ICON_URL:
        errors.append(f"{filename}.headerURL: expected {ICON_URL}")
    if data.get("website") != REPO_WEBSITE:
        errors.append(f"{filename}.website: expected {REPO_WEBSITE}")
    _validate_all_urls(data, filename, errors)

    apps = data.get("apps")
    if not isinstance(apps, list):
        return errors + [f"{filename}.apps: must be an array"]

    bundles = [app.get("bundleIdentifier") for app in apps if isinstance(app, dict)]
    allowed_bundles = config["bundles"]
    required_bundles = config["required_bundles"]
    actual_bundles = set(bundles)
    if (
        not required_bundles.issubset(actual_bundles)
        or not actual_bundles.issubset(allowed_bundles)
        or len(bundles) != len(actual_bundles)
    ):
        errors.append(
            f"{filename}.apps: expected unique allowed bundle IDs "
            f"{sorted(allowed_bundles)} including required {sorted(required_bundles)}"
        )
    _validate_news(data, filename, actual_bundles, errors)

    for index, app in enumerate(apps):
        context = f"{filename}.apps[{index}]"
        if not isinstance(app, dict):
            errors.append(f"{context}: must be an object")
            continue
        if app.get("iconURL") != ICON_URL:
            errors.append(f"{context}.iconURL: expected {ICON_URL}")
        _require_nonempty_strings(app, APP_STRING_FIELDS, context, errors)
        _require_nonempty_strings(app, LEGACY_APP_STRING_FIELDS, context, errors)
        screenshots = app.get("screenshots")
        _validate_screenshots(screenshots, f"{context}.screenshots", errors)
        if screenshots and (
            config["platform"] != "ios"
            or app.get("bundleIdentifier") != "com.stremio.pal"
        ):
            errors.append(f"{context}.screenshots: only the iOS PAL app may use them")
        if (
            not isinstance(app.get("size"), int)
            or isinstance(app.get("size"), bool)
            or app["size"] <= 0
        ):
            errors.append(f"{context}.size: must be a positive integer")
        permissions = app.get("appPermissions")
        if not isinstance(permissions, dict):
            errors.append(f"{context}.appPermissions: must be an object")
        else:
            entitlements = permissions.get("entitlements")
            privacy = permissions.get("privacy")
            if not isinstance(entitlements, list) or not all(
                isinstance(item, str) and item for item in entitlements
            ):
                errors.append(
                    f"{context}.appPermissions.entitlements: "
                    "must be an array of strings"
                )
            if not isinstance(privacy, dict) or not all(
                isinstance(key, str)
                and key
                and isinstance(value, str)
                and value
                for key, value in privacy.items()
            ):
                errors.append(
                    f"{context}.appPermissions.privacy: must be a dictionary of strings"
                )
        versions = app.get("versions")
        if not isinstance(versions, list) or not versions:
            errors.append(f"{context}.versions: must be a non-empty array")
            continue
        for vindex, version in enumerate(versions):
            vcontext = f"{context}.versions[{vindex}]"
            if not isinstance(version, dict):
                errors.append(f"{vcontext}: must be an object")
                continue
            _require_nonempty_strings(
                version, VERSION_STRING_FIELDS, vcontext, errors
            )
            if (
                not isinstance(version.get("size"), int)
                or isinstance(version.get("size"), bool)
                or version["size"] <= 0
            ):
                errors.append(f"{vcontext}.size: must be a positive integer")
        try:
            keys = [version_key(version) for version in versions]
            latest = newest_version(app)
        except (AttributeError, TypeError, ValueError) as exc:
            errors.append(f"{context}.versions: {exc}")
            continue
        if keys != sorted(keys, reverse=True):
            errors.append(
                f"{context}.versions: must be sorted newest-first numerically"
            )

        for app_field, version_field in CURRENT_FIELD_MAP.items():
            if app.get(app_field) != latest.get(version_field):
                errors.append(
                    f"{context}.{app_field}: must mirror newest "
                    f"versions[].{version_field}"
                )

        for vindex, version in enumerate(versions):
            vcontext = f"{context}.versions[{vindex}]"
            if not isinstance(version, dict):
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
    ap.add_argument(
        "files", nargs="*", help="Source files (defaults to both canonical files)"
    )
    args = ap.parse_args()
    paths = (
        [Path(value) for value in args.files]
        if args.files
        else [REPO / filename for filename in SOURCES]
    )
    errors = [error for path in paths for error in validate_file(path)]
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(f"[OK] Validated {len(paths)} source file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
