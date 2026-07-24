from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_cdn  # noqa: E402


def release(version: str, build: str, url: str) -> dict:
    return {
        "version": version,
        "buildVersion": build,
        "date": "2026-07-01",
        "localizedDescription": "Test release",
        "downloadURL": url,
        "size": 123,
        "minOSVersion": "13.0",
    }


class CheckCdnTests(unittest.TestCase):
    def test_failed_link_is_checked_a_second_time(self):
        version = release("1.0.0", "1", "https://example.invalid/app.ipa")
        checks = [("stremio-ios.json", {"name": "Test"}, version)]

        with patch.object(check_cdn, "_status", side_effect=[404, 404]) as status:
            results = check_cdn._check_twice(checks, retry_delay=0)

        self.assertEqual(status.call_count, 2)
        self.assertEqual(results[0][3:], (404, 404))

    def test_successful_link_is_not_checked_twice(self):
        version = release("1.0.0", "1", "https://example.invalid/app.ipa")
        checks = [("stremio-ios.json", {"name": "Test"}, version)]

        with patch.object(check_cdn, "_status", return_value=200) as status:
            results = check_cdn._check_twice(checks, retry_delay=0)

        self.assertEqual(status.call_count, 1)
        self.assertEqual(results[0][3:], (200, None))

    def test_only_two_definitive_missing_responses_are_retired(self):
        missing = release("1.3.0", "1", "https://example.invalid/missing.ipa")
        current = release("1.3.2", "2", "https://example.invalid/current.ipa")
        app = {
            "name": "Stremio Legacy",
            "bundleIdentifier": "com.stremio.one",
            "version": missing["version"],
            "versionDate": missing["date"],
            "versionDescription": missing["localizedDescription"],
            "downloadURL": missing["downloadURL"],
            "size": missing["size"],
            "minOSVersion": missing["minOSVersion"],
            "versions": [current, missing],
        }
        data = {"apps": [app]}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "stremio-ios.json"
            source_path.write_text(json.dumps(data), encoding="utf-8")
            archive_path = root / "unavailable-builds.json"
            with patch.object(check_cdn, "REPO", root):
                retired = check_cdn._retire_confirmed_missing(
                    {"stremio-ios.json": data},
                    [("stremio-ios.json", app, missing, 404, 404)],
                    archive_path,
                    removed_on="2026-07-24",
                )

            saved = json.loads(source_path.read_text(encoding="utf-8"))
            archived = json.loads(archive_path.read_text(encoding="utf-8"))

        self.assertEqual(len(retired), 1)
        self.assertEqual(saved["apps"][0]["versions"], [current])
        self.assertEqual(saved["apps"][0]["version"], "1.3.2")
        self.assertEqual(archived["builds"][0]["removedDate"], "2026-07-24")
        self.assertEqual(archived["builds"][0]["status"], 404)

    def test_ambiguous_retry_is_not_retired(self):
        version = release("1.3.0", "1", "https://example.invalid/app.ipa")
        app = {"name": "Test", "versions": [version]}

        with tempfile.TemporaryDirectory() as directory:
            retired = check_cdn._retire_confirmed_missing(
                {"stremio-ios.json": {"apps": [app]}},
                [("stremio-ios.json", app, version, 404, 503)],
                Path(directory) / "unavailable-builds.json",
            )

        self.assertEqual(retired, [])
        self.assertEqual(app["versions"], [version])


if __name__ == "__main__":
    unittest.main()
