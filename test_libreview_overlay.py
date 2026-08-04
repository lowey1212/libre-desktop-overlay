import datetime as dt
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
    export_recording_data,
    format_glucose,
    find_food_matches,
    load_bundled_uk_foods,
    load_foods,
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

    def test_custom_food_list_is_loaded_and_can_override_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            foods_path = Path(directory) / "foods.json"
            foods_path.write_text('[{"name":"My cereal","serving":"40 g","carbs_g":31}]', encoding="utf-8")
            with patch("libreview_overlay.FOODS_PATH", foods_path):
                foods = load_foods()
        self.assertEqual(foods, [{"name": "My cereal", "serving": "40 g", "carbs_g": 31.0}])

    def test_bundled_uk_food_database_is_cofid_and_has_apple(self):
        foods = load_bundled_uk_foods()
        self.assertGreater(len(foods), 2800)
        apple = next(food for food in foods if food["name"].casefold() == "apples, eating, raw, flesh and skin")
        self.assertEqual(apple["serving"], "100 g")
        self.assertEqual(apple["source"], "UK CoFID 2021")
        self.assertGreaterEqual(apple["carbs_g"], 0)

    def test_food_matches_prioritise_prefix_matches(self):
        foods = [
            {"name": "Pasta with banana", "serving": "100 g", "carbs_g": 20},
            {"name": "Bananas, eating, raw", "serving": "100 g", "carbs_g": 20},
            {"name": "Banana bread", "serving": "100 g", "carbs_g": 50},
        ]
        matches = find_food_matches(foods, "banana")
        self.assertEqual([food["name"] for food in matches], ["Banana bread", "Bananas, eating, raw", "Pasta with banana"])

    def test_export_contains_timestamped_readings_food_and_insulin(self):
        readings = [{"time": dt.datetime(2026, 8, 4, 12, 0), "mgdl": 120, "trend": "→"}]
        events = [
            {"id": "food1", "type": "food", "time": dt.datetime(2026, 8, 4, 12, 5), "description": "Apple", "serving": "1 medium", "carbs_g": 25.0, "note": ""},
            {"id": "insulin1", "type": "insulin", "time": dt.datetime(2026, 8, 4, 12, 10), "insulin_type": "Rapid-acting", "insulin_units": 2.0, "note": ""},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeline.csv"
            export_recording_data(path, readings, events)
            content = path.read_text(encoding="utf-8-sig")
        self.assertIn("2026-08-04T12:05:00", content)
        self.assertIn("Apple", content)
        self.assertIn("Rapid-acting", content)
        self.assertIn("2.0", content)


if __name__ == "__main__":
    unittest.main()
