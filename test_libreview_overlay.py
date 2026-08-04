import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from libre_cloud import CloudSetupError, GlurooSession, _friendly_network_error
from libreview_overlay import (
    GITHUB_REPOSITORY,
    LibreViewOverlay,
    MGDL_PER_MMOLL,
    clamp_overlay_position,
    format_glucose,
    load_libreview_csv,
    load_settings,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class CsvTests(unittest.TestCase):
    def test_mmol_export_is_normalised_to_mgdl(self):
        content = "Device Timestamp,Historic Glucose mmol/L\n04/08/2026 12:30,6.1\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "libre.csv"
            path.write_text(content, encoding="utf-8")
            readings = load_libreview_csv(path)
        self.assertAlmostEqual(readings[0]["mgdl"], 6.1 * MGDL_PER_MMOLL)
        self.assertEqual(format_glucose(readings[0]["mgdl"], "mmol/L"), "6.1")

    def test_mgdl_export_stays_mgdl(self):
        content = "Device Timestamp;Historic Glucose mg/dL\n04/08/2026 12:30;110\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "libre.csv"
            path.write_text(content, encoding="utf-8")
            readings = load_libreview_csv(path)
        self.assertEqual(readings[0]["mgdl"], 110)

    def test_sensor_values_take_precedence_and_duplicates_are_removed(self):
        content = (
            "Device Timestamp,Historic Glucose mg/dL,Strip Glucose mg/dL\n"
            "08/04/2026 01:30 PM,105,140\n"
            "08/04/2026 01:30 PM,108,141\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "libre.csv"
            path.write_text(content, encoding="utf-8")
            readings = load_libreview_csv(path)
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0]["mgdl"], 108)

    def test_implausible_values_are_ignored(self):
        content = (
            "Device Timestamp,Historic Glucose mg/dL\n"
            "04/08/2026 12:25,999\n"
            "04/08/2026 12:30,110\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "libre.csv"
            path.write_text(content, encoding="utf-8")
            readings = load_libreview_csv(path)
        self.assertEqual([item["mgdl"] for item in readings], [110])


class GlurooTests(unittest.TestCase):
    def test_global_connect_url_is_normalised(self):
        session = GlurooSession("https://example.invalid/pebble?token=test-token&count=47")
        self.assertIn("count=288", session._feed_url)
        self.assertIn("token=test-token", session._feed_url)

    def test_gluroo_json_block_builds_url_and_header(self):
        session = GlurooSession(
            '{"url":"https://example.invalid/","apiSecretToken":"test-token",'
            '"apiSecretHeader":"header-value"}'
        )
        self.assertIn("/api/v1/entries/sgv.json", session._feed_url)
        self.assertIn("token=test-token", session._feed_url)
        self.assertEqual(session._headers, {"api-secret": "header-value"})

    def test_gluroo_fragment_without_outer_braces_is_accepted(self):
        session = GlurooSession(
            '"https://example.invalid/","apiSecretToken":"test-token",'
            '"apiSecretHeader":"abcdef012345 does not work as address'
        )
        self.assertIn("token=test-token", session._feed_url)
        self.assertEqual(session._headers, {"api-secret": "abcdef012345"})

    def test_documented_entries_url_is_preserved(self):
        session = GlurooSession(
            "https://example.invalid/api/v1/entries/sgv.json?count=3&token=test-token"
        )
        self.assertIn("/api/v1/entries/sgv.json", session._feed_url)
        self.assertNotIn("/pebble", session._feed_url)

    def test_token_is_required(self):
        with self.assertRaises(CloudSetupError):
            GlurooSession("https://example.invalid/pebble")

    @patch("requests.get")
    def test_pebble_payload_is_converted(self, get):
        get.return_value = FakeResponse({
            "bgs": [
                {"sgv": "101", "datetime": 1_785_840_000_000, "direction": "Flat"},
                {"sgv": "108", "datetime": 1_785_840_300_000, "direction": "FortyFiveUp"},
            ]
        })
        readings = GlurooSession("https://example.invalid/pebble?token=test-token").fetch()
        self.assertEqual([item.mgdl for item in readings], [101, 108])
        self.assertEqual(readings[-1].trend, "↗")

    def test_network_errors_never_echo_the_token_url(self):
        class TokenError(Exception):
            pass

        error = TokenError("failed https://example.invalid/pebble?token=do-not-leak")
        message = _friendly_network_error(error)
        self.assertNotIn("do-not-leak", message)
        self.assertNotIn("https://", message)


class UpdateTests(unittest.TestCase):
    def test_versions_are_compared_numerically(self):
        self.assertGreater(LibreViewOverlay.version_tuple("v1.2.0"), LibreViewOverlay.version_tuple("1.1.9"))

    def test_only_this_repository_release_assets_are_allowed(self):
        good_url = f"https://github.com/{GITHUB_REPOSITORY}/releases/download/v1.0.1/LibreDesktopOverlay-Setup.exe"
        bad_url = "https://example.invalid/LibreDesktopOverlay-Setup.exe"
        self.assertTrue(LibreViewOverlay.is_allowed_update_url(good_url))
        self.assertFalse(LibreViewOverlay.is_allowed_update_url(bad_url))


class SettingsTests(unittest.TestCase):
    def test_invalid_refresh_interval_falls_back_to_one_minute(self):
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "settings.json"
            settings_path.write_text('{"refresh_interval": 999, "auto_check_updates": false}', encoding="utf-8")
            with patch("libreview_overlay.SETTINGS_PATH", settings_path):
                settings = load_settings()
        self.assertEqual(settings["refresh_interval"], 60)
        self.assertFalse(settings["auto_check_updates"])

    def test_overlay_position_keeps_a_visible_margin_on_virtual_desktop(self):
        position = clamp_overlay_position(-5000, 5000, 285, 125, (-1920, 0, 1920, 1080))
        self.assertEqual(position, (-2165, 1040))


if __name__ == "__main__":
    unittest.main()
