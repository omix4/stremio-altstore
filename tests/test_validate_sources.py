from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from source_compat import mirror_current_version  # noqa: E402
from validate_sources import ICON_URL, validate_file, validate_source  # noqa: E402


def version(version: str, build: str, platform: str = "ios") -> dict:
    record = {
        "version": version,
        "buildVersion": build,
        "date": "2026-07-15",
        "localizedDescription": f"Release {version}",
        "downloadURL": (
            f"https://dl.strem.io/apple/{version}b{build}/{platform}/"
            + ("stremio_iOS.ipa" if platform == "ios" else "stremio_tvOS.ipa")
        ),
        "size": 123,
        "sha256": "a" * 64,
        "minOSVersion": "13.0",
    }
    return record


def valid_source(platform: str = "ios") -> dict:
    filename = f"stremio-{platform}.json"
    data = {
        "sourceURL": f"https://repo.omix4.one/{filename}",
        "website": "https://www.stremio.com",
        "iconURL": ICON_URL,
        "headerURL": ICON_URL,
        "apps": [
            {
                "name": "Stremio",
                "bundleIdentifier": "com.stremio.pal",
                "iconURL": ICON_URL,
                "versions": [version("2.10.0", "11", platform)],
            },
            {
                "name": "Stremio Lite",
                "bundleIdentifier": "com.stremio.ios",
                "iconURL": ICON_URL,
                "versions": [version("1.4.0", "12", platform)],
            },
        ],
    }
    for app in data["apps"]:
        mirror_current_version(app)
    return data


class ValidateSourcesTests(unittest.TestCase):
    def test_accepts_compatible_source(self):
        self.assertEqual(validate_source(valid_source(), "stremio-ios.json"), [])

    def test_rejects_non_https_and_unapproved_download_hosts(self):
        data = valid_source()
        data["apps"][0]["versions"][0]["downloadURL"] = "http://evil.example/app.ipa"
        mirror_current_version(data["apps"][0])
        errors = validate_source(data, "stremio-ios.json")
        self.assertTrue(any("HTTPS" in error for error in errors))
        self.assertTrue(any("host must be dl.strem.io" in error for error in errors))

    def test_rejects_noncanonical_icons(self):
        data = valid_source()
        data["iconURL"] = "https://www.stremio.com/missing.png"
        data["apps"][0]["iconURL"] = "https://www.stremio.com/missing.png"
        errors = validate_source(data, "stremio-ios.json")
        self.assertEqual(sum("iconURL: expected" in error for error in errors), 2)

    def test_rejects_bad_hash_bundle_and_stale_mirror(self):
        data = valid_source()
        data["apps"][0]["bundleIdentifier"] = "com.example.unexpected"
        data["apps"][0]["versions"][0]["sha256"] = "not-a-hash"
        data["apps"][0]["version"] = "0.0.1"
        errors = validate_source(data, "stremio-ios.json")
        self.assertTrue(any("expected exactly bundle IDs" in error for error in errors))
        self.assertTrue(any("64 lowercase hex" in error for error in errors))
        self.assertTrue(any("must mirror newest" in error for error in errors))

    def test_rejects_malformed_source_file(self):
        path = Path("stremio-ios.json")
        with patch.object(Path, "read_text", return_value='{"apps": ['):
            errors = validate_file(path)
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot parse source", errors[0])


if __name__ == "__main__":
    unittest.main()
