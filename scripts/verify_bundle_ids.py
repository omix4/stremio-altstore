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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import ipa_plist  # noqa: E402
from ipa_plist import get_main_app_info_plist  # noqa: E402

ipa_plist.USER_AGENT = "stremio-altstore/verify_bundle_ids/1.0"


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
