from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from source_compat import mirror_current_version, sort_versions, version_key  # noqa: E402


def load_updater():
    spec = importlib.util.spec_from_file_location("stremio_updater", REPO / "stremio-updater.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SourceCompatTests(unittest.TestCase):
    def test_semantic_and_build_sorting_is_numeric(self):
        app = {
            "versions": [
                {"version": "2.9.0", "buildVersion": "100"},
                {"version": "2.10.0", "buildVersion": "2"},
                {"version": "2.10.0", "buildVersion": "11"},
            ]
        }
        sort_versions(app)
        self.assertEqual(
            [(v["version"], v["buildVersion"]) for v in app["versions"]],
            [("2.10.0", "11"), ("2.10.0", "2"), ("2.9.0", "100")],
        )
        self.assertGreater(
            version_key({"version": "10.0.0", "buildVersion": "1"}),
            version_key({"version": "2.99.0", "buildVersion": "999"}),
        )

    def test_mirrors_newest_version_to_legacy_app_fields(self):
        latest = {
            "version": "2.10.0",
            "buildVersion": "11",
            "date": "2026-07-15",
            "localizedDescription": "Future release",
            "downloadURL": "https://dl.strem.io/apple/2.10.0b11/ios/stremio_iOS.ipa",
            "size": 123,
            "minOSVersion": "15.0",
        }
        app = {
            "versions": [
                {**latest, "version": "2.9.0", "buildVersion": "99"},
                latest,
            ]
        }
        self.assertTrue(mirror_current_version(app))
        self.assertEqual(app["version"], "2.10.0")
        self.assertEqual(app["versionDate"], "2026-07-15")
        self.assertEqual(app["versionDescription"], "Future release")
        self.assertEqual(app["downloadURL"], latest["downloadURL"])
        self.assertEqual(app["size"], 123)
        self.assertEqual(app["minOSVersion"], "15.0")

    def test_future_release_updates_pal_without_crossing_into_lite(self):
        updater = load_updater()
        source = {
            "apps": [
                {
                    "name": "Stremio",
                    "bundleIdentifier": "com.stremio.pal",
                    "versions": [],
                },
                {
                    "name": "Stremio Lite",
                    "bundleIdentifier": "com.stremio.ios",
                    "versions": [],
                },
            ]
        }
        found = {
            "ios": {
                "2.10.0b2": {
                    "url": "https://dl.strem.io/apple/2.10.0b2/ios/stremio_iOS.ipa",
                    "size": 200,
                    "date": "2026-07-15",
                },
                "1.4.0b12": {
                    "url": "https://dl.strem.io/apple/1.4.0b12/ios/stremio_iOS.ipa",
                    "size": 100,
                    "date": "2026-07-14",
                },
            }
        }
        def plist_for(url):
            tag = url.split("/")[-3]
            version, build = updater.parse_version_tag(tag)
            return {
                "ok": True,
                "plist": {
                    "CFBundleShortVersionString": version,
                    "CFBundleVersion": str(build),
                    "MinimumOSVersion": "13.0",
                },
            }

        with patch.object(updater, "get_main_app_info_plist", side_effect=plist_for):
            new_count, _ = updater.process_platform(
                "ios", source, found, do_info_plist=False, verbose=False
            )
        self.assertEqual(new_count, 2)
        pal, lite = source["apps"]
        self.assertEqual(pal["versions"][0]["version"], "2.10.0")
        self.assertEqual(pal["version"], "2.10.0")
        self.assertEqual(lite["versions"][0]["version"], "1.4.0")
        self.assertEqual(lite["version"], "1.4.0")
        self.assertEqual(pal["bundleIdentifier"], "com.stremio.pal")
        self.assertEqual(lite["bundleIdentifier"], "com.stremio.ios")


if __name__ == "__main__":
    unittest.main()
