#!/usr/bin/env python3
#!/usr/bin/env python3
"""
verify_bundle_ids.py — Standalone IPA Info.plist verifier

For every IPA reference in the JSON sources, this script downloads only the
Info.plist portion via HTTP Range, reads the real bundle identifier, version,
build, and minOS values, and compares them against the JSON entries.

Usage:
    python3 scripts/verify_bundle_ids.py                      # Both JSONs
    python3 scripts/verify_bundle_ids.py stremio-ios.json      # Single file
    python3 scripts/verify_bundle_ids.py --verbose             # Detailed output

Exit codes:
    0 — all values match
    1 — mismatch found
    2 — fetch / parse error
"""

from __future__ import annotations

import json
import plistlib
import struct
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from typing import Optional

UA = "stremio-altstore/verify_bundle_ids/1.0"


def _u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def http_request(url: str, *, method: str = "GET",
                 headers: Optional[dict] = None, timeout: int = 15):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), None
    except Exception:
        return None, {}, None


def get_main_app_info_plist(ipa_url: str) -> dict:
    """Same logic as stremio-updater.py — extracts the main app Info.plist.

    Returns: {"ok": True, "plist": {...}, "name": "..."} or {"ok": False, "error": "..."}
    """
    head = http_request(ipa_url, method="HEAD")
    if head[0] != 200:
        return {"ok": False, "error": f"HEAD {head[0]}"}

    total = int(head[1].get("Content-Length") or 0)
    if not total:
        return {"ok": False, "error": "no Content-Length"}

    tail_size = 64 * 1024 + 22
    start = max(0, total - tail_size)
    _, _, tail = http_request(ipa_url, headers={"Range": f"bytes={start}-{total - 1}"})
    if not tail:
        return {"ok": False, "error": "EOCD fetch"}
    eocd_off = tail.rfind(b"PK\x05\x06")
    if eocd_off < 0:
        return {"ok": False, "error": "no EOCD"}
    cd_offset = _u32(tail, eocd_off + 16)

    cd_limit = min(total - cd_offset, 1024 * 1024)
    _, _, cd = http_request(ipa_url, headers={"Range": f"bytes={cd_offset}-{cd_offset + cd_limit - 1}"})
    if not cd:
        return {"ok": False, "error": "CD fetch"}

    apps = []
    pos = 0
    while pos < len(cd) - 46:
        if cd[pos:pos + 4] != b"PK\x01\x02":
            pos += 1
            continue
        name_len = _u16(cd, pos + 28)
        extra_len = _u16(cd, pos + 30)
        comment_len = _u16(cd, pos + 32)
        local_off = _u32(cd, pos + 42)
        comp_size = _u32(cd, pos + 20)
        method = _u16(cd, pos + 10)
        name = cd[pos + 46:pos + 46 + name_len].decode("utf-8", errors="ignore")
        if name.endswith("/Info.plist") and ".app/" in name \
                and "/Frameworks/" not in name and ".appex/" not in name:
            apps.append((name, local_off, comp_size, method))
        pos += 46 + name_len + extra_len + comment_len

    if not apps:
        return {"ok": False, "error": "no .app/Info.plist"}
    apps.sort(key=lambda e: len(e[0]))
    name, local_off, comp_size, method = apps[0]

    _, _, lfh = http_request(ipa_url, headers={"Range": f"bytes={local_off}-{local_off + 1023}"})
    if not lfh or lfh[:4] != b"PK\x03\x04":
        return {"ok": False, "error": "LFH fetch"}
    fname_len = _u16(lfh, 26)
    extra_len = _u16(lfh, 28)
    data_start = local_off + 30 + fname_len + extra_len

    _, _, payload = http_request(ipa_url, headers={"Range": f"bytes={data_start}-{data_start + comp_size - 1}"})
    if not payload:
        return {"ok": False, "error": "payload fetch"}

    if method == 8:
        try:
            raw = zlib.decompress(payload, -15)
        except zlib.error as e:
            return {"ok": False, "error": f"decompress: {e}"}
    elif method == 0:
        raw = payload
    else:
        return {"ok": False, "error": f"method {method}"}

    try:
        return {"ok": True, "plist": plistlib.loads(raw), "name": name}
    except Exception as e:
        return {"ok": False, "error": f"plist: {e}"}


def verify(json_paths: list[Path], verbose: bool = False) -> int:
    total = 0
    passed = 0
    mismatches = 0
    errors = 0

    for json_path in json_paths:
        if not json_path.exists():
            print(f"[ERR] {json_path} not found")
            errors += 1
            continue

        data = json.loads(json_path.read_text(encoding="utf-8"))
        print(f"\n=== {json_path.name} — {data.get('name', '?')} ===")

        for app in data.get("apps", []):
            bundle = app.get("bundleIdentifier", "?")
            print(f"\n  App: {app.get('name')} ({bundle})")

            for v in app.get("versions", []):
                total += 1
                url = v.get("downloadURL")
                if not url:
                    print(f"    [SKIP] no downloadURL for version {v.get('version')}")
                    continue

                info = get_main_app_info_plist(url)
                if not info.get("ok"):
                    print(f"    [ERR ] {v.get('version')} (build {v.get('buildVersion')}): {info.get('error')}")
                    errors += 1
                    continue

                plist = info["plist"]                                            
                ipa_bundle = plist.get("CFBundleIdentifier", "?")
                ipa_ver = plist.get("CFBundleShortVersionString", "?")
                ipa_build = plist.get("CFBundleVersion", "?")
                ipa_minos = plist.get("MinimumOSVersion", "?")

                json_ver = v.get("version")
                json_build = v.get("buildVersion")
                json_minos = v.get("minOSVersion")

                ok = True
                if ipa_bundle != bundle:
                    print(f"    [DIFF] bundleId: json={bundle!r} ipa={ipa_bundle!r}")
                    ok = False
                if str(ipa_ver) != str(json_ver):
                    print(f"    [DIFF] version: json={json_ver!r} ipa={ipa_ver!r}")
                    ok = False
                if str(ipa_build) != str(json_build):
                    print(f"    [DIFF] build: json={json_build!r} ipa={ipa_build!r}")
                    ok = False
                if str(ipa_minos) != str(json_minos):
                    print(f"    [DIFF] minOS: json={json_minos!r} ipa={ipa_minos!r}")
                    ok = False

                if ok:
                    passed += 1
                    mark = "✓"
                    if verbose:
                        print(f"    [{mark}] {ipa_ver} (build {ipa_build}) bundle={ipa_bundle} minOS={ipa_minos}")
                    else:
                        print(f"    [{mark}] {ipa_ver} build {ipa_build}")
                else:
                    mismatches += 1

    print(f"\n=== Summary ===")
    print(f"Total: {total}, matching: {passed}, mismatches: {mismatches}, errors: {errors}")
    return 1 if (mismatches or errors) else 0


def main() -> int:
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args
    args = [a for a in args if a not in ("--verbose", "-v")]

    here = Path(__file__).parent.parent
    if not args:
        paths = [here / "stremio-ios.json", here / "stremio-tvos.json"]
    else:
        paths = [Path(a) for a in args]

    paths = [p if p.is_absolute() else here / p for p in paths]
    return verify(paths, verbose=verbose)


if __name__ == "__main__":
    sys.exit(main())
