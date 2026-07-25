#!/usr/bin/env python3
"""
stremio-altstore updater
========================
Scans Stremio's dl.strem.io CDN, finds new iOS / tvOS IPA versions, extracts
real bundle identifier, version, minOS data from each IPA's Info.plist
(downloads only the necessary chunks via HTTP Range), and updates the
AltStore-compatible JSON sources.

This script manages two separate JSON files:
    stremio-ios.json   — for iPhone / iPad
    stremio-tvos.json  — for Apple TV

(Why two? Stremio uses the same bundle identifier on both iOS and tvOS:
 com.stremio.pal. Most signing apps do not allow two apps with the same bundle ID
 in a single source, so two files are required.)

Usage
-----
    python3 stremio-updater.py                  # Update both JSONs
    python3 stremio-updater.py --platform ios   # iOS only
    python3 stremio-updater.py --platform tvos  # tvOS only
    python3 stremio-updater.py --dry-run        # Show changes, don't write
    python3 stremio-updater.py --info-plist     # Parse Info.plist from new IPAs
    python3 stremio-updater.py --verbose        # Verbose logging
    python3 stremio-updater.py --source-url-ios  URL   # Update stremio-ios.json sourceURL field
    python3 stremio-updater.py --source-url-tvos URL   # Update stremio-tvos.json sourceURL field

Requirements: Python 3.8+, standard library.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import ipa_plist  # noqa: E402
from ipa_plist import get_main_app_info_plist  # noqa: E402
from source_compat import mirror_current_version, sort_versions, version_key  # noqa: E402

CDN_BASE = "https://dl.strem.io/apple"
OFFICIAL_SOURCE_URL = f"{CDN_BASE}/altstore/source.json"
USER_AGENT = f"stremio-altstore/{__file__}/1.0 (+github-actions)"
ipa_plist.USER_AGENT = USER_AGENT
http_request = ipa_plist.http_request

FRONTIER_BUILD_LOOKAHEAD = 3
INFO_PLIST_ATTEMPTS = 2
MAX_NEWS_ITEMS = 15
NEWS_MAX_AGE_DAYS = 3
PAL_BUNDLE_ID = "com.stremio.pal"

PLATFORMS = {
    "ios":  {"file": "stremio_iOS.ipa",   "label": "iOS",  "json": "stremio-ios.json",
             "pal_bundle": "com.stremio.pal", "lite_bundle": "com.stremio.ios"},
    "tvos": {"file": "stremio_tvOS.ipa",  "label": "tvOS", "json": "stremio-tvos.json",
             "pal_bundle": "com.stremio.pal", "lite_bundle": "com.stremio.ios"},
}

VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+)b(\d+)$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TRACKS = {
    "pal": {"bundle": "com.stremio.pal", "include_next_major": True},
    "lite": {"bundle": "com.stremio.ios", "include_next_major": False},
}


# ----------------------------- Versiyon tarama -----------------------------

def parse_version_tag(tag: str) -> Optional[tuple[str, int]]:
    """'2.0.2b17' -> ('2.0.2', 17)."""
    m = VERSION_RE.match(tag)
    return (m.group(1), int(m.group(2))) if m else None


def parse_semver(version: str) -> Optional[tuple[int, int, int]]:
    """'2.0.6' -> (2, 0, 6)."""
    m = SEMVER_RE.match(version)
    return tuple(map(int, m.groups())) if m else None


def parse_http_date(s: str) -> str:
    """RFC 1123 HTTP date -> 'YYYY-MM-DD'."""
    if not s:
        return ""
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def collect_track_tags(sources: Iterable[dict]) -> dict[str, set[str]]:
    """Collect known version tags independently for PAL and Lite."""
    tags = {track: set() for track in TRACKS}
    bundles = {config["bundle"]: track for track, config in TRACKS.items()}
    for source in sources:
        for app in source.get("apps", []):
            track = bundles.get(app.get("bundleIdentifier"))
            if not track:
                continue
            for version in app.get("versions", []):
                semver = str(version.get("version", ""))
                build = str(version.get("buildVersion", ""))
                tag = f"{semver}b{build}"
                if parse_version_tag(tag):
                    tags[track].add(tag)
    return tags


def generate_frontier_tags(
    known_tags: Iterable[str], *, include_next_major: bool
) -> set[str]:
    """Generate a small, pattern-based search frontier from the newest tag."""
    parsed = []
    for tag in known_tags:
        version_build = parse_version_tag(tag)
        if not version_build:
            continue
        version, build = version_build
        semver = parse_semver(version)
        if semver:
            parsed.append((semver, build))
    if not parsed:
        return set()

    (major, minor, patch), build = max(parsed)
    candidates: set[str] = set()
    for offset in range(1, FRONTIER_BUILD_LOOKAHEAD + 1):
        candidate_build = build + offset
        versions = {(major, minor, patch)}
        versions.update((major, minor, patch + step) for step in range(1, offset + 1))
        versions.add((major, minor + 1, 0))
        if include_next_major:
            versions.add((major + 1, 0, 0))
        for candidate_version in versions:
            semver = ".".join(map(str, candidate_version))
            candidates.add(f"{semver}b{candidate_build}")
    return candidates


def _official_screenshot_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "mzstatic.com" or host.endswith(".mzstatic.com")
    )


def validate_official_screenshots(value: object) -> Optional[dict]:
    """Return a safe copy of official iPhone/iPad screenshots, or None."""
    if not isinstance(value, dict) or not value:
        return None
    if not set(value).issubset({"iphone", "ipad"}):
        return None

    validated: dict[str, list] = {}
    for device, entries in value.items():
        if not isinstance(entries, list) or not entries or len(entries) > 10:
            return None
        safe_entries = []
        for entry in entries:
            if isinstance(entry, str):
                if not _official_screenshot_url(entry):
                    return None
                safe_entries.append(entry)
                continue
            if not isinstance(entry, dict) or not set(entry).issubset(
                {"imageURL", "width", "height"}
            ):
                return None
            if not _official_screenshot_url(entry.get("imageURL")):
                return None
            for dimension in ("width", "height"):
                if dimension in entry and (
                    not isinstance(entry[dimension], int)
                    or isinstance(entry[dimension], bool)
                    or entry[dimension] <= 0
                ):
                    return None
            safe_entries.append(copy.deepcopy(entry))
        validated[device] = safe_entries
    return validated


def fetch_official_metadata(*, verbose: bool = False) -> dict:
    """Return whitelisted PAL releases and screenshots; failure is advisory."""
    empty = {"releases": {}, "screenshots": None}
    response = http_request(OFFICIAL_SOURCE_URL, timeout=15)
    if response.status != 200 or not response.body:
        print(f"[WARN] Official source unavailable (HTTP {response.status}); continuing with CDN frontier")
        return empty
    try:
        source = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[WARN] Official source is invalid JSON ({exc}); continuing with CDN frontier")
        return empty

    if not isinstance(source, dict) or not isinstance(source.get("apps"), list):
        print("[WARN] Official source has an unexpected structure; continuing with CDN frontier")
        return empty

    releases: dict[str, dict] = {}
    screenshots = None
    for app in source.get("apps", []):
        if not isinstance(app, dict) or app.get("bundleIdentifier") != PAL_BUNDLE_ID:
            continue
        screenshots = validate_official_screenshots(app.get("screenshots"))
        versions = app.get("versions")
        if not isinstance(versions, list):
            continue
        for release in versions:
            if not isinstance(release, dict):
                continue
            version = release.get("version")
            build = release.get("buildVersion")
            if not isinstance(version, str) or not parse_semver(version):
                continue
            if not str(build).isdigit():
                continue
            tag = f"{version}b{int(build)}"
            metadata = {}
            for field in ("date", "localizedDescription", "minOSVersion"):
                value = release.get(field)
                if isinstance(value, str) and value.strip():
                    metadata[field] = value
            releases[tag] = metadata
    if verbose:
        screenshot_count = sum(len(items) for items in (screenshots or {}).values())
        print(
            f"[INFO] Official source supplied {len(releases)} PAL release hint(s) "
            f"and {screenshot_count} screenshot(s)"
        )
    return {"releases": releases, "screenshots": screenshots}


def fetch_official_releases(*, verbose: bool = False) -> dict[str, dict]:
    """Compatibility helper returning only whitelisted PAL release metadata."""
    return fetch_official_metadata(verbose=verbose)["releases"]


def build_candidate_tags(
    track_tags: dict[str, set[str]], official_releases: dict[str, dict]
) -> set[str]:
    candidates = set(official_releases)
    for track, config in TRACKS.items():
        candidates.update(
            generate_frontier_tags(
                track_tags.get(track, set()),
                include_next_major=config["include_next_major"],
            )
        )
    return candidates


def scan_cdn(
    candidate_tags: Iterable[str],
    *,
    official_releases: Optional[dict[str, dict]] = None,
    verbose: bool = False,
    max_workers: int = 16,
) -> dict[str, dict[str, dict]]:
    """
    Scans an already bounded and deduplicated set of CDN candidates in parallel.
    Returns: {platform: {tag: {url, size, date}}}
    """
    official_releases = official_releases or {}
    tags = sorted(set(candidate_tags))
    candidates: list[tuple[str, str, str]] = []  # (platform, tag, url)
    for plat, info in PLATFORMS.items():
        for tag in tags:
            url = f"{CDN_BASE}/{tag}/{plat}/{info['file']}"
            candidates.append((plat, tag, url))

    targets: dict[str, dict[str, dict]] = {"ios": {}, "tvos": {}}

    def check(cand: tuple[str, str, str]) -> Optional[tuple[str, str, dict]]:
        plat, tag, url = cand
        resp = http_request(url, method="HEAD", timeout=8)
        if resp.status != 200:
            return None
        size = int(resp.headers.get("Content-Length") or 0)
        date = parse_http_date(resp.headers.get("Last-Modified", ""))
        return (
            plat,
            tag,
            {
                "url": url,
                "size": size,
                "date": date,
                "official": official_releases.get(tag, {}),
            },
        )

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for result in ex.map(check, candidates):
            if result is None:
                continue
            plat, tag, meta = result
            targets[plat][tag] = meta
            if verbose:
                print(f"  [{plat}] HIT {tag} -> {meta['size']:,} bytes, {meta['date']}")

    return targets


# ----------------------------- Source update ----------------------------

def get_or_create_app(source: dict, name: str, bundle_id: str, tint: str) -> dict:
    for app in source["apps"]:
        if app["bundleIdentifier"] == bundle_id:
            return app
    app = {
        "name": name,
        "bundleIdentifier": bundle_id,
        "developerName": "Stremio",
        "subtitle": "Freedom to stream.",
        "localizedDescription": f"{name} — Stremio unofficial AltStore port.",
        "iconURL": "https://repo.omix4.one/assets/stremio-icon.png",
        "tintColor": tint,
        "category": "entertainment",
        "screenshots": [],
        "appPermissions": {"entitlements": [], "privacy": {}},
        "versions": [],
    }
    source["apps"].append(app)
    return app


def sync_official_screenshots(source: dict, screenshots: Optional[dict]) -> bool:
    """Sync standard and legacy-compatible screenshots to the PAL listing."""
    if screenshots is None:
        return False

    screenshot_urls = [
        entry if isinstance(entry, str) else entry["imageURL"]
        for entry in screenshots.get("iphone", [])
    ]
    for app in source.get("apps", []):
        if app.get("bundleIdentifier") != PAL_BUNDLE_ID:
            continue
        if (
            app.get("screenshots") == screenshots
            and app.get("screenshotURLs") == screenshot_urls
        ):
            return False
        app["screenshots"] = copy.deepcopy(screenshots)
        app["screenshotURLs"] = copy.deepcopy(screenshot_urls)
        return True
    return False


def merge_version(app: dict, version: str, build: int, meta: dict, info: Optional[dict]) -> bool:
    """If the same version exists, refresh its metadata; otherwise append it. Returns True if anything changed."""
    official = meta.get("official") or {}
    preferred_date = official.get("date") or meta.get("date")
    preferred_description = official.get("localizedDescription")
    preferred_min_os = (
        (info or {}).get("MinimumOSVersion")
        or official.get("minOSVersion")
    )
    for v in app["versions"]:
        if v.get("version") == version and v.get("buildVersion") == str(build):
            changed = False
            if v.get("size") != meta["size"]:
                v["size"] = meta["size"]; changed = True
            if preferred_date and v.get("date") != preferred_date:
                v["date"] = preferred_date; changed = True
            if preferred_description and v.get("localizedDescription") != preferred_description:
                v["localizedDescription"] = preferred_description; changed = True
            if preferred_min_os and v.get("minOSVersion") != preferred_min_os:
                v["minOSVersion"] = preferred_min_os; changed = True
            sort_versions(app)
            if mirror_current_version(app):
                changed = True
            return changed

    min_os = preferred_min_os or "13.0"
    new_v = {
        "version": version,
        "buildVersion": str(build),
        "date": preferred_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "localizedDescription": (
            preferred_description or f"{app['name']} {version} (build {build})."
        ),
        "downloadURL": meta["url"],
        "size": meta["size"],
        "minOSVersion": min_os,
    }
    app.setdefault("versions", []).append(new_v)
    sort_versions(app)
    mirror_current_version(app)
    return True


def process_platform(
    plat: str,
    source: dict,
    found: dict,
    *,
    do_info_plist: bool,
    verbose: bool,
) -> tuple[int, int, list[dict]]:
    info = PLATFORMS[plat]

    managed_bundles = {info["pal_bundle"], info["lite_bundle"]}
    previous_latest = {bundle: None for bundle in managed_bundles}
    for app in source.get("apps", []):
        if app.get("bundleIdentifier") not in managed_bundles:
            continue
        versions = app.get("versions", [])
        previous_latest[app["bundleIdentifier"]] = (
            max((version_key(item) for item in versions), default=None)
        )

    new_count = 0
    update_count = 0
    new_releases: list[dict] = []
    for tag, meta in found.get(plat, {}).items():
        pv = parse_version_tag(tag)
        if not pv:
            continue
        version, build = pv

        # 1.x = Lite, 2.x = PAL
        if version.startswith("1."):
            target = get_or_create_app(
                source, "Stremio Lite", info["lite_bundle"], "#8A5AAB"
            )
        else:
            target = get_or_create_app(
                source, "Stremio", info["pal_bundle"], "#7055D9"
            )

        # Already known? New IPAs are always verified against their embedded
        # metadata. --info-plist additionally refreshes that metadata for known IPAs.
        was_known = any(v.get("version") == version and v.get("buildVersion") == str(build)
                        for v in target["versions"])

        info_plist = None
        if not was_known or do_info_plist:
            plist_result = {"ok": False, "error": "not attempted"}
            for _ in range(INFO_PLIST_ATTEMPTS):
                plist_result = get_main_app_info_plist(meta["url"])
                if plist_result.get("ok"):
                    break
            if plist_result.get("ok"):
                info_plist = plist_result["plist"]
                ipa_version = str(info_plist.get("CFBundleShortVersionString", ""))
                ipa_build = str(info_plist.get("CFBundleVersion", ""))
                if ipa_version != version or ipa_build != str(build):
                    print(
                        f"  [WARN] {plat}/{tag} rejected: Info.plist reports "
                        f"{ipa_version or '?'}b{ipa_build or '?'}"
                    )
                    continue
                ipa_bundle = str(info_plist.get("CFBundleIdentifier", ""))
                expected_bundle = str(target.get("bundleIdentifier", ""))
                if ipa_bundle != expected_bundle:
                    print(
                        f"  [WARN] {plat}/{tag} rejected: Info.plist bundle ID "
                        f"{ipa_bundle or '?'} does not match {expected_bundle or '?'}"
                    )
                    continue
            elif verbose:
                print(f"  [WARN] {plat}/{tag} Info.plist parse: {plist_result.get('error')}")
            if not was_known and not info_plist:
                print(f"  [WARN] {plat}/{tag} rejected: unable to verify Info.plist")
                continue

        effective_meta = meta
        if plat != "ios" and meta.get("official", {}).get("minOSVersion"):
            # The official PAL source describes the iOS marketplace artifact.
            # Its minimum OS must not replace the tvOS IPA's verified value.
            effective_meta = {
                **meta,
                "official": {
                    key: value
                    for key, value in meta["official"].items()
                    if key != "minOSVersion"
                },
            }

        if merge_version(target, version, build, effective_meta, info_plist):
            if was_known:
                update_count += 1
                if verbose:
                    print(f"  [UPDATE] {plat}/{tag} metadata refreshed")
            else:
                new_count += 1
                release = next(
                    item
                    for item in target["versions"]
                    if item.get("version") == version
                    and item.get("buildVersion") == str(build)
                )
                old_latest = previous_latest[target["bundleIdentifier"]]
                new_releases.append(
                    {
                        "platform": plat,
                        "appName": target["name"],
                        "appID": target["bundleIdentifier"],
                        "version": version,
                        "buildVersion": str(build),
                        "date": release["date"],
                        "isForwardRelease": (
                            old_latest is None or version_key(release) > old_latest
                        ),
                    }
                )
                print(f"  [NEW] {plat}/{tag} -> added ({meta['size'] // 1024 // 1024} MB, {meta.get('date')})")
    for app in source.get("apps", []):
        if app.get("bundleIdentifier") not in managed_bundles:
            continue
        if not app.get("versions"):
            continue
        sort_versions(app)
        if mirror_current_version(app):
            update_count += 1
    return new_count, update_count, new_releases


def _recent_release(release_date: str, today: date) -> bool:
    try:
        published = date.fromisoformat(release_date)
    except (TypeError, ValueError):
        return False
    age = (today - published).days
    return 0 <= age <= NEWS_MAX_AGE_DAYS


def _news_caption(app_name: str, version: str, build: str, platforms: set[str]) -> str:
    if platforms == {"ios", "tvos"}:
        availability = "iOS, iPadOS, and tvOS"
    elif platforms == {"ios"}:
        availability = "iOS and iPadOS"
    else:
        availability = "tvOS"
    return f"{app_name} {version} (build {build}) is now available for {availability}."


def generate_release_news(
    sources: dict[str, dict], new_releases: Iterable[dict], *, today: Optional[date] = None
) -> set[str]:
    """Add deterministic future-release news and return changed platforms."""
    today = today or datetime.now(timezone.utc).date()
    eligible = [
        event
        for event in new_releases
        if event.get("isForwardRelease")
        and _recent_release(str(event.get("date", "")), today)
    ]
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for event in eligible:
        key = (event["appID"], event["version"], event["buildVersion"])
        grouped.setdefault(key, []).append(event)

    changed: set[str] = set()
    for (app_id, version, build), events in grouped.items():
        platforms = {event["platform"] for event in events}
        platform_suffix = "-".join(
            platform for platform in ("ios", "tvos") if platform in platforms
        )
        identifier = f"release-{app_id}-{version}-b{build}-{platform_suffix}"
        app_name = events[0]["appName"]
        news_item = {
            "title": f"{app_name} {version} released",
            "identifier": identifier,
            "caption": _news_caption(app_name, version, build, platforms),
            "date": max(event["date"] for event in events),
            "tintColor": "#7055D9",
            "notify": True,
            "appID": app_id,
        }
        for platform in platforms:
            source = sources.get(platform)
            if source is None:
                continue
            news = source.setdefault("news", [])
            if any(item.get("identifier") == identifier for item in news):
                continue
            news.append(copy.deepcopy(news_item))
            news.sort(
                key=lambda item: (str(item.get("date", "")), str(item.get("identifier", ""))),
                reverse=True,
            )
            del news[MAX_NEWS_ITEMS:]
            changed.add(platform)
    return changed


# ---------------------------------- Main -----------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--platform", choices=["ios", "tvos", "all"], default="all",
                    help="Which platform to update (default: all)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show changes but do not write the files")
    ap.add_argument("--info-plist", action="store_true",
                    help="Parse Info.plist from discovered IPAs (slower, ~100KB/IPA)")
    ap.add_argument("--source-url-ios", metavar="URL", help="Update the sourceURL field of stremio-ios.json")
    ap.add_argument("--source-url-tvos", metavar="URL", help="Update the sourceURL field of stremio-tvos.json")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = ap.parse_args()

    here = Path(__file__).parent
    platforms_to_run = (["ios", "tvos"] if args.platform == "all" else [args.platform])

    total_new = 0
    total_updated = 0
    loaded_sources: dict[str, tuple[Path, dict]] = {}
    for plat in platforms_to_run:
        json_path = here / PLATFORMS[plat]["json"]
        if not json_path.exists():
            print(f"[WARN] {json_path} not found, skipping.")
            continue
        loaded_sources[plat] = (
            json_path,
            json.loads(json_path.read_text(encoding="utf-8")),
        )

    track_tags = collect_track_tags(source for _, source in loaded_sources.values())
    for track in TRACKS:
        if args.verbose:
            print(f"[INFO] Known {track.upper()} versions: {len(track_tags[track])}")

    official_metadata = fetch_official_metadata(verbose=args.verbose)
    official_releases = official_metadata["releases"]
    candidates = build_candidate_tags(track_tags, official_releases)
    frontier_count = len(candidates - set(official_releases))
    print(
        f"[INFO] Scanning {len(candidates)} unique release tag(s) "
        f"({frontier_count} frontier, {len(official_releases)} official hint(s))"
    )
    found = scan_cdn(
        candidates,
        official_releases=official_releases,
        verbose=args.verbose,
    )

    platform_changes: dict[str, list[int]] = {}
    new_releases: list[dict] = []
    for plat, (json_path, source) in loaded_sources.items():
        print(f"\n=== {PLATFORMS[plat]['label']} ===")

        platform_updated = 0

        # Source URL update
        url_key = f"source_url_{plat}"
        url_flag = getattr(args, url_key, None)
        if url_flag:
            if source.get("sourceURL") != url_flag:
                source["sourceURL"] = url_flag
                platform_updated += 1
                print(f"[UPDATE] sourceURL = {url_flag}")

        if plat == "ios" and sync_official_screenshots(
            source, official_metadata["screenshots"]
        ):
            platform_updated += 1
            print("[UPDATE] Synced official iPhone/iPad screenshots")

        new_count, update_count, platform_releases = process_platform(
            plat,
            source,
            found,
            do_info_plist=args.info_plist,
            verbose=args.verbose,
        )
        platform_updated += update_count
        new_releases.extend(platform_releases)
        platform_changes[plat] = [new_count, platform_updated]
        total_new += new_count
        total_updated += platform_updated

    news_changed = generate_release_news(
        {plat: source for plat, (_, source) in loaded_sources.items()},
        new_releases,
    )
    for plat in sorted(news_changed):
        platform_changes[plat][1] += 1
        total_updated += 1
        print(f"[UPDATE] {plat}: added release news")

    for plat, (json_path, source) in loaded_sources.items():
        new_count, update_count = platform_changes[plat]
        if args.dry_run:
            if new_count or update_count:
                print(f"[DRY-RUN] {plat}: +{new_count} new, ~{update_count} updated (not written)")
            continue

        # Yaz
        json_path.write_text(
            json.dumps(source, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if new_count or update_count:
            print(f"[OK] {json_path.name} updated (+{new_count} new, ~{update_count} updated)")
        else:
            print(f"[OK] {json_path.name} already up to date")

    print(f"\n=== Summary ===")
    print(f"New: {total_new}, Updated: {total_updated}")
    if args.dry_run and (total_new or total_updated):
        print("(DRY-RUN mode: files not written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
