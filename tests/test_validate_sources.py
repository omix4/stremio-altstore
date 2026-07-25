from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from source_compat import mirror_current_version  # noqa: E402
from validate_sources import (  # noqa: E402
    ICON_URL,
    REPO_WEBSITE,
    validate_file,
    validate_source,
)


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
        "name": "Stremio test source",
        "sourceURL": f"https://repo.omix4.one/{filename}",
        "website": REPO_WEBSITE,
        "iconURL": ICON_URL,
        "headerURL": ICON_URL,
        "news": [],
        "apps": [
            {
                "name": "Stremio",
                "bundleIdentifier": "com.stremio.pal",
                "developerName": "Stremio",
                "localizedDescription": "Stremio test app",
                "iconURL": ICON_URL,
                "screenshots": [],
                "appPermissions": {"entitlements": [], "privacy": {}},
                "versions": [version("2.10.0", "11", platform)],
            },
            {
                "name": "Stremio Lite",
                "bundleIdentifier": "com.stremio.ios",
                "developerName": "Stremio",
                "localizedDescription": "Stremio Lite test app",
                "iconURL": ICON_URL,
                "screenshots": [],
                "appPermissions": {"entitlements": [], "privacy": {}},
                "versions": [version("1.4.0", "12", platform)],
            },
        ],
    }
    if platform == "ios":
        data["apps"].append(
            {
                "name": "Stremio Legacy",
                "bundleIdentifier": "com.stremio.one",
                "developerName": "Stremio",
                "localizedDescription": "Stremio legacy test app",
                "iconURL": ICON_URL,
                "screenshots": [],
                "appPermissions": {"entitlements": [], "privacy": {}},
                "versions": [version("1.3.2", "2", platform)],
            }
        )
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
        self.assertTrue(any("expected unique allowed bundle IDs" in error for error in errors))
        self.assertTrue(any("64 lowercase hex" in error for error in errors))
        self.assertTrue(any("must mirror newest" in error for error in errors))

    def test_allows_optional_legacy_app_to_be_fully_retired(self):
        data = valid_source()
        data["apps"] = [
            app
            for app in data["apps"]
            if app["bundleIdentifier"] != "com.stremio.one"
        ]

        self.assertEqual(validate_source(data, "stremio-ios.json"), [])

    def test_rejects_missing_modern_and_legacy_required_fields(self):
        data = valid_source()
        del data["name"]
        del data["apps"][0]["developerName"]
        del data["apps"][0]["versionDate"]
        del data["apps"][0]["versions"][0]["buildVersion"]
        errors = validate_source(data, "stremio-ios.json")
        self.assertTrue(
            any(".name: must be a non-empty string" in error for error in errors)
        )
        self.assertTrue(
            any(
                ".developerName: must be a non-empty string" in error
                for error in errors
            )
        )
        self.assertTrue(
            any(
                ".versionDate: must be a non-empty string" in error
                for error in errors
            )
        )
        self.assertTrue(any(".buildVersion" in error for error in errors))

    def test_rejects_invalid_permissions_and_sizes(self):
        data = valid_source()
        data["apps"][0]["appPermissions"] = {
            "entitlements": "not-an-array",
            "privacy": [],
        }
        data["apps"][0]["size"] = 0
        data["apps"][0]["versions"][0]["size"] = "123"
        errors = validate_source(data, "stremio-ios.json")
        self.assertTrue(
            any("entitlements: must be an array" in error for error in errors)
        )
        self.assertTrue(
            any("privacy: must be a dictionary" in error for error in errors)
        )
        self.assertEqual(
            sum("size: must be a positive integer" in error for error in errors), 2
        )

    def test_accepts_official_screenshots_and_release_news(self):
        data = valid_source()
        data["apps"][0]["screenshots"] = {
            "iphone": ["https://is1-ssl.mzstatic.com/image/phone.jpg"],
            "ipad": [
                {
                    "imageURL": "https://is1-ssl.mzstatic.com/image/tablet.jpg",
                    "width": 2048,
                    "height": 2732,
                }
            ],
        }
        data["news"] = [
            {
                "title": "Stremio 2.10.0 released",
                "identifier": "release-com.stremio.pal-2.10.0-b11-ios",
                "caption": "Stremio 2.10.0 is available for iOS and iPadOS.",
                "date": "2026-07-15",
                "tintColor": "#7055D9",
                "notify": True,
                "appID": "com.stremio.pal",
            }
        ]
        self.assertEqual(validate_source(data, "stremio-ios.json"), [])

    def test_rejects_invalid_screenshots_and_news(self):
        data = valid_source()
        data["apps"][0]["screenshots"] = [
            "https://evil.example/screenshot.png"
        ]
        item = {
            "title": "Release",
            "identifier": "duplicate",
            "caption": "A release.",
            "date": "2026-02-30",
            "tintColor": "purple",
            "notify": "yes",
            "appID": "com.example.missing",
        }
        data["news"] = [item, dict(item)]
        errors = validate_source(data, "stremio-ios.json")
        self.assertTrue(any("mzstatic.com" in error for error in errors))
        self.assertTrue(any("real calendar date" in error for error in errors))
        self.assertTrue(any("identifiers must be unique" in error for error in errors))
        self.assertTrue(any("notify: must be a boolean" in error for error in errors))
        self.assertTrue(any("appID" in error for error in errors))

    def test_rejects_malformed_source_file(self):
        path = Path("stremio-ios.json")
        with patch.object(Path, "read_text", return_value='{"apps": ['):
            errors = validate_file(path)
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot parse source", errors[0])


if __name__ == "__main__":
    unittest.main()
