from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))


def load_updater():
    spec = importlib.util.spec_from_file_location(
        "stremio_updater_discovery", REPO / "stremio-updater.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class UpdaterDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.updater = load_updater()

    def test_frontier_follows_release_pattern_without_literal_versions(self):
        pal = self.updater.generate_frontier_tags(
            {"2.0.5b20"}, include_next_major=True
        )
        lite = self.updater.generate_frontier_tags(
            {"1.3.6b7"}, include_next_major=False
        )

        self.assertIn("2.0.6b21", pal)
        self.assertIn("2.0.5b21", pal)
        self.assertIn("2.0.7b22", pal)
        self.assertIn("2.0.8b23", pal)
        self.assertIn("2.1.0b21", pal)
        self.assertIn("3.0.0b21", pal)
        self.assertEqual(len(pal), 15)
        self.assertIn("1.3.7b8", lite)
        self.assertIn("1.4.0b8", lite)
        self.assertNotIn("2.0.0b8", lite)
        self.assertEqual(len(lite), 12)

    def test_normal_frontier_is_capped_at_54_head_requests(self):
        tags = self.updater.build_candidate_tags(
            {"pal": {"2.0.5b20"}, "lite": {"1.3.6b7"}}, {}
        )
        calls = []

        def not_found(url, **kwargs):
            calls.append((url, kwargs))
            return self.updater.ipa_plist.HttpResp(404, {}, None)

        with patch.object(self.updater, "http_request", side_effect=not_found):
            self.updater.scan_cdn(tags)

        self.assertEqual(len(tags), 27)
        self.assertEqual(len(calls), 54)
        self.assertTrue(all(call[1]["method"] == "HEAD" for call in calls))

    def test_official_source_is_optional_and_whitelists_metadata(self):
        source = {
            "apps": [
                {
                    "bundleIdentifier": "com.stremio.pal",
                    "versions": [
                        {
                            "version": "2.0.6",
                            "buildVersion": "21",
                            "date": "2026-07-22",
                            "localizedDescription": "Official notes",
                            "minOSVersion": "13.0",
                            "downloadURL": "https://example.invalid/manifest.json",
                            "size": 999,
                        }
                    ],
                }
            ]
        }
        response = self.updater.ipa_plist.HttpResp(
            200, {}, json.dumps(source).encode()
        )
        with patch.object(self.updater, "http_request", return_value=response):
            releases = self.updater.fetch_official_releases()

        self.assertEqual(
            releases,
            {
                "2.0.6b21": {
                    "date": "2026-07-22",
                    "localizedDescription": "Official notes",
                    "minOSVersion": "13.0",
                }
            },
        )

        invalid = self.updater.ipa_plist.HttpResp(200, {}, b'{"apps":')
        with patch.object(self.updater, "http_request", return_value=invalid):
            self.assertEqual(self.updater.fetch_official_releases(), {})

    def test_official_hint_outside_frontier_is_added_once(self):
        official = {"9.9.9b99": {"localizedDescription": "Future"}}
        tags = self.updater.build_candidate_tags(
            {"pal": {"2.0.5b20"}, "lite": {"1.3.6b7"}}, official
        )
        self.assertIn("9.9.9b99", tags)
        self.assertEqual(len(tags), 28)

    def test_existing_release_is_enriched_from_official_metadata(self):
        app = {
            "name": "Stremio",
            "bundleIdentifier": "com.stremio.pal",
            "versions": [
                {
                    "version": "2.0.6",
                    "buildVersion": "21",
                    "date": "2026-07-21",
                    "localizedDescription": "Generated notes",
                    "downloadURL": "https://dl.strem.io/apple/2.0.6b21/ios/stremio_iOS.ipa",
                    "size": 100,
                    "minOSVersion": "12.0",
                }
            ],
        }
        source = {
            "apps": [
                app,
                {
                    "name": "Stremio Lite",
                    "bundleIdentifier": "com.stremio.ios",
                    "versions": [],
                },
            ]
        }
        found = {
            "ios": {
                "2.0.6b21": {
                    "url": app["versions"][0]["downloadURL"],
                    "size": 101,
                    "date": "2026-07-21",
                    "official": {
                        "date": "2026-07-22",
                        "localizedDescription": "Official notes",
                        "minOSVersion": "13.0",
                    },
                }
            }
        }

        new_count, update_count = self.updater.process_platform(
            "ios", source, found, do_info_plist=False, verbose=False
        )

        self.assertEqual(new_count, 0)
        self.assertGreaterEqual(update_count, 1)
        release = app["versions"][0]
        self.assertEqual(release["localizedDescription"], "Official notes")
        self.assertEqual(release["date"], "2026-07-22")
        self.assertEqual(release["minOSVersion"], "13.0")
        self.assertEqual(release["size"], 101)
        self.assertNotIn("official", release)

        release["minOSVersion"] = "15.0"
        found["tvos"] = found.pop("ios")
        self.updater.process_platform(
            "tvos", source, found, do_info_plist=False, verbose=False
        )
        self.assertEqual(release["minOSVersion"], "15.0")

    def test_new_release_requires_matching_info_plist(self):
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
                "2.0.6b21": {
                    "url": "https://dl.strem.io/apple/2.0.6b21/ios/stremio_iOS.ipa",
                    "size": 100,
                    "date": "2026-07-22",
                    "official": {},
                }
            }
        }
        mismatch = {
            "ok": True,
            "plist": {
                "CFBundleShortVersionString": "2.0.5",
                "CFBundleVersion": "20",
            },
        }
        with patch.object(
            self.updater, "get_main_app_info_plist", return_value=mismatch
        ):
            new_count, _ = self.updater.process_platform(
                "ios", source, found, do_info_plist=False, verbose=False
            )
        self.assertEqual(new_count, 0)
        self.assertEqual(source["apps"][0]["versions"], [])

        transient_failure = {"ok": False, "error": "temporary range failure"}
        verified = {
            "ok": True,
            "plist": {
                "CFBundleShortVersionString": "2.0.6",
                "CFBundleVersion": "21",
                "MinimumOSVersion": "13.0",
            },
        }
        with patch.object(
            self.updater,
            "get_main_app_info_plist",
            side_effect=[transient_failure, verified],
        ) as plist:
            new_count, _ = self.updater.process_platform(
                "ios", source, found, do_info_plist=False, verbose=False
            )
        self.assertEqual(plist.call_count, 2)
        self.assertEqual(new_count, 1)
        self.assertEqual(source["apps"][0]["versions"][0]["version"], "2.0.6")


if __name__ == "__main__":
    unittest.main()
