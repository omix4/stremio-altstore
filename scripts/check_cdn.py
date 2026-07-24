#!/usr/bin/env python3
"""Check listed IPA links and optionally retire confirmed missing builds.

Every listed IPA is checked once. A failed request is checked a second time
after a short delay. With ``--prune-unavailable``, only links that return 404
or 410 on both checks are removed from the AltStore source and recorded in
``unavailable-builds.json``. Other repeated failures remain critical so a CDN
outage or an ambiguous response cannot silently remove releases.

Exit codes:
    0 — healthy, warnings allowed, or confirmed missing builds were retired
    2 — CRITICAL: at least one failure could not be safely retired
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ipa_plist import http_request  # noqa: E402
from source_compat import mirror_current_version  # noqa: E402

SOURCES = ["stremio-ios.json", "stremio-tvos.json"]
ARCHIVE = "unavailable-builds.json"
DEFAULT_MAX_AGE_DAYS = 45
DEFAULT_RETRY_DELAY_SECONDS = 2.0
GONE_STATUSES = {404, 410}


def _newest(data: dict) -> dict | None:
    """Newest version across all apps in a source, by (version, build)."""
    best = None
    best_key = None
    for app in data.get("apps", []):
        for version in app.get("versions", []):
            parts = [
                int(chunk) if chunk.isdigit() else -1
                for chunk in str(version.get("version", "")).split(".")
            ]
            try:
                build = int(version.get("buildVersion", 0))
            except (TypeError, ValueError):
                build = 0
            key = (parts, build)
            if best_key is None or key > best_key:
                best_key, best = key, version
    return best


def _listed_versions(data: dict) -> list[tuple[dict, dict]]:
    """Return every catalogued release with its containing app."""
    return [
        (app, version)
        for app in data.get("apps", [])
        for version in app.get("versions", [])
        if isinstance(version, dict)
    ]


def _age_days(date_str: str) -> int | None:
    try:
        release_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (date.today() - release_date).days


def _status(version: dict) -> int | None:
    url = version.get("downloadURL", "")
    return http_request(
        url,
        method="HEAD",
        headers={"Cache-Control": "no-cache"},
        timeout=15,
    ).status


def _check_twice(
    checks: list[tuple[str, dict, dict]], retry_delay: float
) -> list[tuple[str, dict, dict, int | None, int | None]]:
    """Check everything once, then retry only failed links."""
    workers = min(12, max(1, len(checks)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        first_statuses = list(executor.map(lambda item: _status(item[2]), checks))

    retry_indexes = [
        index for index, status in enumerate(first_statuses) if status != 200
    ]
    second_statuses: dict[int, int | None] = {}
    if retry_indexes:
        if retry_delay > 0:
            time.sleep(retry_delay)
        retry_versions = [checks[index][2] for index in retry_indexes]
        with ThreadPoolExecutor(max_workers=min(12, len(retry_versions))) as executor:
            retried = executor.map(_status, retry_versions)
            second_statuses = dict(zip(retry_indexes, retried))

    return [
        (*candidate, first_statuses[index], second_statuses.get(index))
        for index, candidate in enumerate(checks)
    ]


def _archive_entry(
    source: str, app: dict, version: dict, status: int, removed_on: str
) -> dict:
    return {
        "source": source,
        "platform": "tvOS" if source == "stremio-tvos.json" else "iOS / iPadOS",
        "appName": str(app.get("name", "?")),
        "bundleIdentifier": str(app.get("bundleIdentifier", "")),
        "version": version.get("version"),
        "buildVersion": version.get("buildVersion"),
        "releaseDate": version.get("date"),
        "downloadURL": version.get("downloadURL"),
        "removedDate": removed_on,
        "status": status,
    }


def _retire_confirmed_missing(
    source_data: dict[str, dict],
    results: list[tuple[str, dict, dict, int | None, int | None]],
    archive_path: Path,
    removed_on: str | None = None,
) -> list[dict]:
    """Remove twice-confirmed missing versions and append archive records."""
    removed_on = removed_on or date.today().isoformat()
    if archive_path.exists():
        archive = json.loads(archive_path.read_text(encoding="utf-8"))
    else:
        archive = {"builds": []}
    archived_urls = {
        entry.get("downloadURL") for entry in archive.get("builds", [])
    }
    retired: list[dict] = []

    for source, app, version, first, second in results:
        if first not in GONE_STATUSES or second not in GONE_STATUSES:
            continue
        assert isinstance(second, int)
        versions = app.get("versions", [])
        if version not in versions:
            continue
        versions.remove(version)
        entry = _archive_entry(source, app, version, second, removed_on)
        retired.append(entry)
        if entry["downloadURL"] not in archived_urls:
            archive.setdefault("builds", []).append(entry)
            archived_urls.add(entry["downloadURL"])
        if versions:
            mirror_current_version(app)
        else:
            source_data[source]["apps"].remove(app)

    if not retired:
        return []

    for source, data in source_data.items():
        (REPO / source).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    archive["builds"].sort(
        key=lambda entry: (
            str(entry.get("removedDate", "")),
            str(entry.get("source", "")),
            str(entry.get("appName", "")),
            str(entry.get("version", "")),
            str(entry.get("buildVersion", "")),
        ),
        reverse=True,
    )
    archive_path.write_text(
        json.dumps(archive, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return retired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="Freshness warning threshold (default: CDN_MAX_AGE_DAYS or 45)",
    )
    parser.add_argument(
        "--prune-unavailable",
        action="store_true",
        help="retire links confirmed missing by two consecutive 404/410 responses",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help="delay before rechecking a failed link (default: 2)",
    )
    args = parser.parse_args(argv)
    max_age = (
        args.max_age_days
        if args.max_age_days is not None
        else int(os.environ.get("CDN_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS))
    )

    critical: list[str] = []
    warnings: list[str] = []
    checks: list[tuple[str, dict, dict]] = []
    source_data: dict[str, dict] = {}

    print("=== CDN health check ===")
    for source in SOURCES:
        path = REPO / source
        if not path.exists():
            critical.append(f"{source}: file not found")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        source_data[source] = data
        newest = _newest(data)
        if not newest:
            warnings.append(f"{source}: no versions listed")
            print(f"  {source}: (no versions)")
            continue

        versions = _listed_versions(data)
        checks.extend((source, app, version) for app, version in versions)
        label = f"{newest.get('version')} build {newest.get('buildVersion')}"
        line = f"  {source}: newest {label}, {len(versions)} listed IPA(s)"
        age = _age_days(newest.get("date", ""))
        if age is not None:
            line += f", {age}d old"
        print(line)
        if age is not None and age > max_age:
            warnings.append(
                f"{source}: newest version {label} is {age} days old "
                f"(> {max_age}d threshold) — scanner may be missing releases, "
                "or Stremio has not shipped"
            )

    print("\n=== Listed IPA reachability ===")
    results = _check_twice(checks, max(0, args.retry_delay_seconds))
    retired = (
        _retire_confirmed_missing(source_data, results, REPO / ARCHIVE)
        if args.prune_unavailable
        else []
    )
    retired_urls = {entry["downloadURL"] for entry in retired}

    for source, app, version, first, second in results:
        label = f"{version.get('version')} build {version.get('buildVersion')}"
        prefix = f"{source} · {app.get('name', '?')} {label}"
        if first == 200:
            print(f"  {prefix} → HTTP 200")
            continue
        print(f"  {prefix} → HTTP {first}; retry HTTP {second}")
        url = version.get("downloadURL", "")
        if url in retired_urls:
            print(f"  [REMOVED] {prefix} — confirmed unavailable and archived")
            continue
        critical.append(
            f"{source}: {app.get('name', '?')} {label} unreachable "
            f"(HTTP {first}, retry HTTP {second}) — {url}"
        )

    print()
    for warning in warnings:
        print(f"[WARN] {warning}")
    for message in critical:
        print(f"[CRITICAL] {message}")

    if critical:
        print("\nResult: CRITICAL — one or more downloads could not be safely retired.")
        return 2
    if retired:
        print(f"\nResult: retired {len(retired)} confirmed unavailable build(s).")
        return 0
    if warnings:
        print("\nResult: OK with warnings.")
        return 0
    print("\nResult: healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
