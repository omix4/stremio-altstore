"""Shared compatibility helpers for the Stremio AltStore sources."""

from __future__ import annotations

import re
from typing import Any

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

CURRENT_FIELD_MAP = {
    "version": "version",
    "versionDate": "date",
    "versionDescription": "localizedDescription",
    "downloadURL": "downloadURL",
    "size": "size",
    "minOSVersion": "minOSVersion",
}


def semantic_version_key(version: Any) -> tuple[int, ...]:
    """Return a numeric key for a dotted release version.

    Raises ``ValueError`` instead of silently applying lexical sorting to an
    invalid version. Source validation reports that error with file context.
    """
    value = str(version)
    if not SEMVER_RE.fullmatch(value):
        raise ValueError(f"invalid numeric semantic version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def build_number(build: Any) -> int:
    """Return a numeric build number or raise ``ValueError``."""
    value = str(build)
    if not value.isdigit():
        raise ValueError(f"invalid numeric build version: {value!r}")
    return int(value)


def version_key(version: dict) -> tuple[tuple[int, ...], int]:
    """Return the numeric semantic-version/build sort key for a version record."""
    return semantic_version_key(version.get("version")), build_number(
        version.get("buildVersion")
    )


def sort_versions(app: dict) -> None:
    """Sort an app's versions newest-first using numeric comparisons."""
    app.setdefault("versions", []).sort(key=version_key, reverse=True)


def newest_version(app: dict) -> dict:
    """Return an app's newest nested version using numeric comparisons."""
    versions = app.get("versions")
    if not isinstance(versions, list) or not versions:
        raise ValueError("app has no versions")
    return max(versions, key=version_key)


def mirror_current_version(app: dict) -> bool:
    """Mirror the newest nested release into legacy app-level source fields."""
    latest = newest_version(app)
    changed = False
    for app_field, version_field in CURRENT_FIELD_MAP.items():
        value = latest.get(version_field)
        if app.get(app_field) != value:
            app[app_field] = value
            changed = True
    return changed
