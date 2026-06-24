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
import json
import plistlib
import re
import struct
import sys
import urllib.error
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, NamedTuple, Optional
from xml.etree import ElementTree as ET

CDN_BASE = "https://dl.strem.io/apple"
USER_AGENT = f"stremio-altstore/{__file__}/1.0 (+github-actions)"

PLATFORMS = {
    "ios":  {"file": "stremio_iOS.ipa",   "label": "iOS",  "json": "stremio-ios.json",
             "pal_bundle": "com.stremio.pal", "lite_bundle": "com.stremio.ios"},
    "tvos": {"file": "stremio_tvOS.ipa",  "label": "tvOS", "json": "stremio-tvos.json",
             "pal_bundle": "com.stremio.pal", "lite_bundle": "com.stremio.ios"},
}

VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+)b(\d+)$")


# ----------------------------- HTTP helpers -----------------------------

class HttpResp(NamedTuple):
    status: Optional[int]
    headers: dict
    body: Optional[bytes]


def http_request(url: str, *, method: str = "GET", headers: Optional[dict] = None,
                 timeout: int = 15) -> HttpResp:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return HttpResp(r.status, dict(r.headers), r.read())
    except urllib.error.HTTPError as e:
        return HttpResp(e.code, dict(e.headers or {}), None)
    except Exception:
        return HttpResp(None, {}, None)


# ------------------------- IPA Info.plist extractor --------------------------

def _u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def get_main_app_info_plist(ipa_url: str) -> dict:
    """
    IPA URL'inden ana app Info.plist'ini parse eder.
    Only the main app's Info.plist is read (framework and appex entries are excluded).
    Method: only the ZIP End-of-Central-Directory and Central Directory sections are
    fetched via HTTP Range; the relevant payload is then downloaded.
    Typical download: < 100 KB.

    Returns: {"ok": True, "plist": {...}, "name": "Payload/..."}
         veya {"ok": False, "error": "..."}
    """
    head = http_request(ipa_url, method="HEAD")
    if head.status != 200:
        return {"ok": False, "error": f"HEAD {head.status}"}
    total = int(head.headers.get("Content-Length") or 0)
    if total <= 0:
        return {"ok": False, "error": "no Content-Length"}

    # 1) ZIP sonundaki EOCD record'u bul
    tail_size = 64 * 1024 + 22
    start = max(0, total - tail_size)
    tail = http_request(ipa_url, headers={"Range": f"bytes={start}-{total - 1}"})
    if tail.status not in (200, 206) or not tail.body:
        return {"ok": False, "error": "EOCD fetch"}
    eocd_off = tail.body.rfind(b"PK\x05\x06")
    if eocd_off < 0:
        return {"ok": False, "error": "EOCD signature not found"}
    cd_offset = _u32(tail.body, eocd_off + 16)

    # 2) Central directory'yi oku (max 1 MB)
    cd_limit = min(total - cd_offset, 1024 * 1024)
    cd = http_request(ipa_url, headers={"Range": f"bytes={cd_offset}-{cd_offset + cd_limit - 1}"})
    if cd.status not in (200, 206) or not cd.body:
        return {"ok": False, "error": "CD fetch"}

    # 3) Collect all ".app/Info.plist" entries, pick the main app
    entries: list[tuple[str, int, int, int]] = []
    pos = 0
    while pos < len(cd.body) - 46:
        if cd.body[pos:pos + 4] != b"PK\x01\x02":
            pos += 1
            continue
        name_len = _u16(cd.body, pos + 28)
        extra_len = _u16(cd.body, pos + 30)
        comment_len = _u16(cd.body, pos + 32)
        local_off = _u32(cd.body, pos + 42)
        comp_size = _u32(cd.body, pos + 20)
        method = _u16(cd.body, pos + 10)
        name = cd.body[pos + 46:pos + 46 + name_len].decode("utf-8", errors="ignore")
        if name.endswith("/Info.plist"):
            entries.append((name, local_off, comp_size, method))
        pos += 46 + name_len + extra_len + comment_len

    if not entries:
        return {"ok": False, "error": "no Info.plist entry"}

    apps = [e for e in entries
            if ".app/Info.plist" in e[0]
            and "/Frameworks/" not in e[0]
            and ".appex/" not in e[0]]
    if not apps:
        return {"ok": False, "error": "no .app/Info.plist entry"}
    apps.sort(key=lambda e: len(e[0]))  # shortest path = main app
    name, local_off, comp_size, method = apps[0]

    # 4) Read filename+extra lengths from the local file header
    lfh = http_request(ipa_url, headers={"Range": f"bytes={local_off}-{local_off + 1023}"})
    if lfh.status not in (200, 206) or not lfh.body or lfh.body[:4] != b"PK\x03\x04":
        return {"ok": False, "error": "LFH fetch"}
    fname_len = _u16(lfh.body, 26)
    extra_len = _u16(lfh.body, 28)
    data_start = local_off + 30 + fname_len + extra_len

    # 5) Fetch the compressed payload
    payload = http_request(ipa_url, headers={"Range": f"bytes={data_start}-{data_start + comp_size - 1}"})
    if payload.status not in (200, 206) or not payload.body:
        return {"ok": False, "error": "payload fetch"}

    if method == 8:
        try:
            raw = zlib.decompress(payload.body, -15)
        except zlib.error as e:
            return {"ok": False, "error": f"decompress: {e}"}
    elif method == 0:
        raw = payload.body
    else:
        return {"ok": False, "error": f"unsupported method {method}"}

    # 6) Plist'i parse et (XML veya binary — plistlib her ikisini de destekler)
    try:
        return {"ok": True, "plist": plistlib.loads(raw), "name": name}
    except Exception as e:
        return {"ok": False, "error": f"plist parse: {e}"}


# ----------------------------- Versiyon tarama -----------------------------

def parse_version_tag(tag: str) -> Optional[tuple[str, int]]:
    """'2.0.2b17' -> ('2.0.2', 17)."""
    m = VERSION_RE.match(tag)
    return (m.group(1), int(m.group(2))) if m else None


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


def scan_cdn(known_tags: Iterable[str], *, verbose: bool = False, max_workers: int = 16) -> dict[str, dict[str, dict]]:
    """
    Scans the CDN in parallel. Tries the last known build + buffer range.
    Returns: {platform: {tag: {url, size, date}}}
    """
    known = set(known_tags)
    max_build = 0
    known_semvers: set[str] = set()
    for tag in known:
        pv = parse_version_tag(tag)
        if pv:
            max_build = max(max_build, pv[1])
            known_semvers.add(pv[0])

    # Most likely major.minor values: known + a few plausible next ones
    next_candidates = ["2.0.3", "2.1.0", "2.1.1", "1.3.7", "1.4.0", "2.0.4", "2.0.5"]
    semvers = list(known_semvers | set(next_candidates))

    # Scan only the last known build + buffer range (new releases are rare)
    build_range = range(max_build, max_build + 8)

    # Build candidate list
    candidates: list[tuple[str, str, str]] = []  # (platform, tag, url)
    for plat, info in PLATFORMS.items():
        for semver in semvers:
            for build in build_range:
                tag = f"{semver}b{build}"
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
        return (plat, tag, {"url": url, "size": size, "date": date})

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
        "iconURL": "https://www.stremio.com/website/stremio-logo-small.png",
        "tintColor": tint,
        "category": "entertainment",
        "screenshots": [],
        "appPermissions": {"entitlements": [], "privacy": {}},
        "versions": [],
    }
    source["apps"].append(app)
    return app


def merge_version(app: dict, version: str, build: int, meta: dict, info: Optional[dict]) -> bool:
    """If the same version exists, refresh its metadata; otherwise append it. Returns True if anything changed."""
    for v in app["versions"]:
        if v.get("version") == version and v.get("buildVersion") == str(build):
            changed = False
            if v.get("size") != meta["size"]:
                v["size"] = meta["size"]; changed = True
            if meta.get("date") and v.get("date") != meta["date"]:
                v["date"] = meta["date"]; changed = True
            if info and info.get("MinimumOSVersion") and v.get("minOSVersion") != info["MinimumOSVersion"]:
                v["minOSVersion"] = info["MinimumOSVersion"]; changed = True
            return changed

    min_os = (info or {}).get("MinimumOSVersion") or "13.0"
    new_v = {
        "version": version,
        "buildVersion": str(build),
        "date": meta.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "localizedDescription": f"{app['name']} {version} (build {build}).",
        "downloadURL": meta["url"],
        "size": meta["size"],
        "minOSVersion": min_os,
    }
    app.setdefault("versions", []).append(new_v)
    app["versions"].sort(
        key=lambda v: (v.get("version", ""), int(v.get("buildVersion", "0"))),
        reverse=True,
    )
    return True


def process_platform(plat: str, source: dict, found: dict, *, do_info_plist: bool, verbose: bool) -> tuple[int, int]:
    info = PLATFORMS[plat]
    pal_app = get_or_create_app(source, "Stremio", info["pal_bundle"], "#7055D9")
    lite_app = get_or_create_app(source, "Stremio Lite", info["lite_bundle"], "#8A5AAB")

    new_count = 0
    update_count = 0
    for tag, meta in found.get(plat, {}).items():
        pv = parse_version_tag(tag)
        if not pv:
            continue
        version, build = pv

        info_plist = None
        if do_info_plist:
            plist_result = get_main_app_info_plist(meta["url"])
            if plist_result.get("ok"):
                info_plist = plist_result["plist"]
            elif verbose:
                print(f"  [WARN] {plat}/{tag} Info.plist parse: {plist_result.get('error')}")

        # 1.x = Lite, 2.x = PAL
        target = lite_app if version.startswith("1.") else pal_app

        # Already known? (Was it already in the source file?)
        was_known = any(v.get("version") == version and v.get("buildVersion") == str(build)
                        for v in target["versions"])

        if merge_version(target, version, build, meta, info_plist):
            if was_known:
                update_count += 1
                if verbose:
                    print(f"  [UPDATE] {plat}/{tag} metadata refreshed")
            else:
                new_count += 1
                print(f"  [NEW] {plat}/{tag} -> added ({meta['size'] // 1024 // 1024} MB, {meta.get('date')})")
    return new_count, update_count


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
    for plat in platforms_to_run:
        json_path = here / PLATFORMS[plat]["json"]
        if not json_path.exists():
            print(f"[WARN] {json_path} not found, skipping.")
            continue

        print(f"\n=== {PLATFORMS[plat]['label']} ===")
        source = json.loads(json_path.read_text(encoding="utf-8"))

        # Bilinen tag'leri topla
        known_tags: set[str] = set()
        for app in source["apps"]:
            for v in app.get("versions", []):
                ver = v.get("version", "")
                bv = v.get("buildVersion", "")
                if ver and bv:
                    known_tags.add(f"{ver}b{bv}")
        print(f"[INFO] Bilinen versiyon: {len(known_tags)}")

        if args.verbose:
            for t in sorted(known_tags):
                print(f"  - {t}")

        print("[INFO] Scanning CDN...")
        found = scan_cdn(known_tags, verbose=args.verbose)

        # Source URL update
        url_key = f"source_url_{plat}"
        url_flag = getattr(args, url_key, None)
        if url_flag:
            if source.get("sourceURL") != url_flag:
                source["sourceURL"] = url_flag
                total_updated += 1
                print(f"[UPDATE] sourceURL = {url_flag}")

        new_count, update_count = process_platform(plat, source, found,
                                                    do_info_plist=args.info_plist,
                                                    verbose=args.verbose)
        total_new += new_count
        total_updated += update_count

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
