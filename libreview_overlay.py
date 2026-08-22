import csv
import ctypes
import datetime as dt
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import webbrowser
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

try:
    import winreg
except ImportError:
    winreg = None

import requests

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None

from libre_cloud import (
    CloudLoginError,
    CloudSetupError,
    GlurooSession,
    JugglucoSession,
)


FILE_REFRESH_MS = 60_000
CLOUD_REFRESH_MS = 60_000
APP_VERSION = "1.0.33"
GITHUB_REPOSITORY = "lowey1212/libre-desktop-overlay"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases"
UPDATE_ASSET_NAME = "LibreDesktopOverlay-Setup.exe"
UPDATE_MAX_BYTES = 100 * 1024 * 1024
REFRESH_INTERVAL_OPTIONS = (30, 60, 120)
VISUAL_SETTINGS_KEYS = (
    "unit",
    "always_on_top",
    "overlay_color",
    "overlay_background_opacity",
    "overlay_number_opacity",
    "overlay_size",
    "overlay_locked",
    "overlay_x",
    "overlay_y",
)
WARNING_AFTER_MINUTES = 5
STALE_AFTER_MINUTES = 10
MGDL_PER_MMOLL = 18.0182
CREDENTIAL_SERVICE = "LibreView Desktop Overlay"
WINDOWS_STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_STARTUP_VALUE = "LibreDesktopOverlay"
APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.cwd())) / "LibreViewDesktopOverlay"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"
EVENTS_PATH = APP_DATA_DIR / "events.json"
FOODS_PATH = APP_DATA_DIR / "foods.json"
UK_COFID_PATH = Path(__file__).resolve().parent / "data" / "uk_cofid_foods.json"
FOODDATA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
FOODDATA_API_CREDENTIAL = "fooddata-central-api-key"
COFID_SOURCE_URL = "https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid"
FOOD_REGION_OPTIONS = ("UK — CoFID 2021 offline database", "USA — USDA FoodData Central API")
LIVE_SOURCE_LABELS = {"Juggluco": "Juggluco — Local", "Gluroo": "Gluroo — Cloud"}
CSV_SOURCE_LABEL = "LibreView CSV — Local fallback"
OVERLAY_COLORS = {
    "Navy": "#0f172a",
    "Black": "#050505",
    "Purple": "#2e1065",
    "Forest": "#064e3b",
    "Slate": "#1e293b",
}
OVERLAY_SIZES = {
    "Small": {"width": 230, "height": 100, "value_font": ("Segoe UI", 25, "bold"), "trend_font": ("Segoe UI", 19, "bold"), "unit_font": ("Segoe UI", 8), "time_font": ("Segoe UI", 8)},
    "Medium": {"width": 285, "height": 125, "value_font": ("Segoe UI", 31, "bold"), "trend_font": ("Segoe UI", 24, "bold"), "unit_font": ("Segoe UI", 9), "time_font": ("Segoe UI", 9)},
    "Large": {"width": 360, "height": 155, "value_font": ("Segoe UI", 40, "bold"), "trend_font": ("Segoe UI", 30, "bold"), "unit_font": ("Segoe UI", 11), "time_font": ("Segoe UI", 11)},
}
OVERLAY_TRANSPARENT_COLOR = "#ff00ff"
WINDOWS_GWL_EXSTYLE = -20
WINDOWS_GWLP_WNDPROC = -4
WINDOWS_WS_EX_LAYERED = 0x00080000
WINDOWS_WS_EX_TRANSPARENT = 0x00000020
WINDOWS_WM_NCHITTEST = 0x0084
WINDOWS_WM_MOUSEACTIVATE = 0x0021
WINDOWS_HTTRANSPARENT = -1
WINDOWS_MA_NOACTIVATE = 3
INSULIN_TYPE_OPTIONS = ("Rapid-acting", "Long-acting", "Mixed", "Other")
EVENT_COLORS = {"food": "#ca8a04", "insulin": "#dc2626"}
FOOD_REFERENCE_SOURCE = "UK CoFID 2021 values per 100 g / user edits"
COMMON_FOODS = [
    {"name": "Apple", "serving": "1 medium", "carbs_g": 25.0},
    {"name": "Banana", "serving": "1 medium", "carbs_g": 27.0},
    {"name": "Orange", "serving": "1 medium", "carbs_g": 15.0},
    {"name": "Pear", "serving": "1 medium", "carbs_g": 27.0},
    {"name": "Grapes", "serving": "100 g", "carbs_g": 18.0},
    {"name": "Strawberries", "serving": "100 g", "carbs_g": 8.0},
    {"name": "Blueberries", "serving": "100 g", "carbs_g": 15.0},
    {"name": "White bread", "serving": "1 slice", "carbs_g": 14.0},
    {"name": "Wholemeal bread", "serving": "1 slice", "carbs_g": 17.0},
    {"name": "Toast", "serving": "1 slice", "carbs_g": 14.0},
    {"name": "Cooked rice", "serving": "100 g", "carbs_g": 28.0},
    {"name": "Cooked pasta", "serving": "100 g", "carbs_g": 31.0},
    {"name": "Potato", "serving": "1 medium", "carbs_g": 26.0},
    {"name": "Breakfast cereal", "serving": "30 g", "carbs_g": 24.0},
    {"name": "Porridge oats", "serving": "40 g dry", "carbs_g": 24.0},
    {"name": "Semi-skimmed milk", "serving": "200 ml", "carbs_g": 10.0},
    {"name": "Plain yoghurt", "serving": "125 g", "carbs_g": 6.0},
    {"name": "Fruit yoghurt", "serving": "125 g", "carbs_g": 18.0},
    {"name": "Baked beans", "serving": "Half a tin", "carbs_g": 27.0},
    {"name": "Pizza", "serving": "1 medium slice", "carbs_g": 30.0},
    {"name": "Chocolate", "serving": "25 g", "carbs_g": 14.0},
    {"name": "Crisps", "serving": "25 g bag", "carbs_g": 13.0},
    {"name": "Biscuit", "serving": "1 biscuit", "carbs_g": 8.0},
    {"name": "Sugar", "serving": "1 teaspoon", "carbs_g": 4.0},
]


def clamp_overlay_position(x, y, width, height, bounds, margin=40):
    """Keep enough of an overlay visible across a multi-monitor desktop."""
    left, top, right, bottom = bounds
    min_x = left - width + margin
    max_x = right - margin
    min_y = top - height + margin
    max_y = bottom - margin
    return max(min_x, min(int(x), max_x)), max(min_y, min(int(y), max_y))


def parse_number(value):
    if value is None:
        return None
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_timestamp(value):
    if not value:
        return None
    text = str(value).strip()
    formats = [
        "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %I:%M %p", "%d/%m/%Y %I:%M %p", "%m/%d/%Y %I:%M %p",
        "%d-%m-%Y %I:%M:%S %p", "%d/%m/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M:%S %p",
    ]
    for fmt in formats:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        return None


def find_column(row, candidates):
    lowered = {str(key).strip().lower(): key for key in row.keys()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    for key in row.keys():
        key_text = str(key).lower()
        if any(candidate.lower() in key_text for candidate in candidates):
            return key
    return None


def load_libreview_csv(path):
    rows = None
    last_error = None
    for encoding in ["utf-8-sig", "utf-16", "cp1252"]:
        try:
            with open(path, "r", encoding=encoding, newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel
                rows = list(csv.DictReader(handle, dialect=dialect))
            break
        except UnicodeError as error:
            last_error = error
    if rows is None:
        raise ValueError(f"Could not read the CSV file: {last_error}")
    if not rows:
        raise ValueError("The CSV file contains no readings.")

    timestamp_col = find_column(rows[0], ["Device Timestamp", "Timestamp", "Date Time"])
    def glucose_priority(column):
        name = str(column).strip().lower()
        if "glucose" not in name or "unit" in name:
            return 99
        if "historic" in name:
            return 0
        if "scan" in name:
            return 1
        if "sensor" in name or name.startswith("glucose"):
            return 2
        if "strip" in name:
            return 3
        return 99

    glucose_cols = sorted(
        [key for key in rows[0].keys() if glucose_priority(key) < 99],
        key=glucose_priority,
    )
    if not timestamp_col or not glucose_cols:
        raise ValueError(
            "This does not look like a LibreView export. Expected timestamp and glucose columns."
        )

    readings_by_time = {}
    for row in rows:
        timestamp = parse_timestamp(row.get(timestamp_col))
        if not timestamp:
            continue
        for glucose_col in glucose_cols:
            glucose = parse_number(row.get(glucose_col))
            if glucose is None:
                continue
            mgdl = glucose * MGDL_PER_MMOLL if "mmol" in glucose_col.lower() else glucose
            if not 20 <= mgdl <= 600:
                continue
            readings_by_time[timestamp] = {"time": timestamp, "mgdl": mgdl, "trend": ""}
            break
    if not readings_by_time:
        raise ValueError("No usable glucose readings were found in the CSV.")
    return sorted(readings_by_time.values(), key=lambda item: item["time"])


def display_value(mgdl, unit):
    return mgdl / MGDL_PER_MMOLL if unit == "mmol/L" else mgdl


def format_glucose(mgdl, unit):
    value = display_value(mgdl, unit)
    return f"{value:.1f}" if unit == "mmol/L" else f"{value:.0f}"


def scale_carbs_for_gram_serving(serving, base_serving, base_carbs):
    """Scale a food's carbs when both servings are explicit gram amounts."""
    gram_pattern = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(g|gram|grams|kg|kilogram|kilograms)?\b", re.I)

    def grams(value, allow_bare=False):
        match = gram_pattern.search(str(value or ""))
        if not match:
            return None
        if not match.group(2):
            bare_value = str(value or "").strip()
            if not allow_bare or not re.fullmatch(r"\d+(?:[.,]\d+)?", bare_value):
                return None
        amount = float(match.group(1).replace(",", "."))
        unit = (match.group(2) or "g").casefold()
        return amount * (1000 if unit.startswith("k") else 1)

    try:
        original_grams = grams(base_serving, allow_bare=True)
        current_grams = grams(serving, allow_bare=original_grams is not None)
        original_carbs = float(base_carbs)
    except (TypeError, ValueError):
        return None
    if not original_grams or current_grams is None or original_carbs < 0:
        return None
    return round(original_carbs * current_grams / original_grams, 1)


def format_event_tooltip(event):
    timestamp = event.get("time")
    if isinstance(timestamp, dt.datetime):
        timestamp = timestamp.strftime("%d %b %Y %H:%M")
    else:
        timestamp = str(timestamp or "Unknown time")
    if event.get("type") == "food":
        lines = ["Food", str(event.get("description") or "Unknown food"), f"Time: {timestamp}"]
        if event.get("serving"):
            lines.append(f"Serving: {event['serving']}")
        if isinstance(event.get("carbs_g"), (int, float)):
            lines.append(f"Carbohydrates: {event['carbs_g']:g} g")
    else:
        lines = ["Insulin", f"Type: {event.get('insulin_type') or 'Other'}", f"Time: {timestamp}"]
        if isinstance(event.get("insulin_units"), (int, float)):
            lines.append(f"Injected: {event['insulin_units']:g} units")
    if event.get("note"):
        lines.append(f"Note: {event['note']}")
    return "\n".join(lines)


def load_settings():
    defaults = {
        "unit": "mmol/L",
        "gluroo_remember": False,
        "live_provider": "Juggluco",
        "juggluco_host": "",
        "juggluco_port": 17580,
        "juggluco_remember": False,
        "overlay_enabled": False,
        "overlay_color": "Navy",
        "overlay_opacity": 82,
        "overlay_background_opacity": 82,
        "overlay_number_opacity": 100,
        "overlay_size": "Medium",
        "overlay_locked": False,
        "overlay_x": 30,
        "overlay_y": 30,
        "start_overlay": False,
        "start_hidden": False,
        "start_with_windows": False,
        "refresh_interval": 60,
        "auto_check_updates": True,
        "always_on_top": True,
    }
    data = {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
        defaults.update({key: data[key] for key in defaults if key in data})
    except (OSError, ValueError, TypeError):
        pass
    legacy_opacity = defaults.get("overlay_opacity", 82)
    try:
        legacy_opacity = max(35, min(100, int(legacy_opacity)))
    except (TypeError, ValueError):
        legacy_opacity = 82
    defaults["overlay_background_opacity"] = data.get("overlay_background_opacity", legacy_opacity)
    defaults["overlay_number_opacity"] = data.get("overlay_number_opacity", 100)
    for key in ["overlay_background_opacity", "overlay_number_opacity"]:
        try:
            defaults[key] = max(35, min(100, int(defaults[key])))
        except (TypeError, ValueError):
            defaults[key] = 82 if key == "overlay_background_opacity" else 100
    for key in ["overlay_x", "overlay_y"]:
        try:
            defaults[key] = int(defaults[key])
        except (TypeError, ValueError):
            defaults[key] = 30
    if defaults.get("overlay_size") not in OVERLAY_SIZES:
        defaults["overlay_size"] = "Medium"
    if defaults.get("overlay_color") not in OVERLAY_COLORS:
        defaults["overlay_color"] = "Navy"
    try:
        defaults["refresh_interval"] = int(defaults.get("refresh_interval", 60))
    except (TypeError, ValueError):
        defaults["refresh_interval"] = 60
    if defaults["refresh_interval"] not in REFRESH_INTERVAL_OPTIONS:
        defaults["refresh_interval"] = 60
    if "live_provider" not in data:
        defaults["live_provider"] = "Gluroo" if defaults.get("gluroo_remember") else "Juggluco"
    if defaults.get("live_provider") not in {"Juggluco", "Gluroo"}:
        defaults["live_provider"] = "Juggluco"
    try:
        defaults["juggluco_port"] = int(defaults.get("juggluco_port", 17580))
    except (TypeError, ValueError):
        defaults["juggluco_port"] = 17580
    defaults["auto_check_updates"] = bool(defaults.get("auto_check_updates", True))
    defaults["start_with_windows"] = bool(defaults.get("start_with_windows", False))
    if "start_overlay" not in data:
        defaults["start_overlay"] = bool(defaults.get("overlay_enabled", False))
    return defaults


def windows_startup_command():
    """Return a hidden-startup command for the source or packaged app."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        return f'"{executable}"'
    executable = Path(sys.executable).resolve()
    if executable.name.casefold() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw
    script = Path(__file__).resolve()
    return f'"{executable}" "{script}"'


def set_windows_startup(enabled):
    """Register or unregister this app for the current Windows user."""
    if winreg is None:
        return False
    try:
        if enabled:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, WINDOWS_STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, WINDOWS_STARTUP_VALUE, 0, winreg.REG_SZ, windows_startup_command())
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, WINDOWS_STARTUP_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def save_settings(settings):
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_events():
    try:
        data = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    events = []
    for item in data:
        if not isinstance(item, dict) or item.get("type") not in ("food", "insulin"):
            continue
        timestamp = parse_timestamp(item.get("time"))
        if not timestamp:
            continue
        event = {
            "id": str(item.get("id") or uuid.uuid4().hex),
            "type": item["type"],
            "time": timestamp,
            "note": str(item.get("note") or "").strip(),
        }
        if event["type"] == "food":
            description = str(item.get("description") or "").strip()
            if not description:
                continue
            event["description"] = description
            event["serving"] = str(item.get("serving") or "").strip()
            event["carbs_g"] = item.get("carbs_g")
        else:
            insulin_type = str(item.get("insulin_type") or "Other").strip() or "Other"
            try:
                units = float(item.get("insulin_units"))
            except (TypeError, ValueError):
                continue
            if units <= 0:
                continue
            event["insulin_type"] = insulin_type
            event["insulin_units"] = units
        events.append(event)
    return sorted(events, key=lambda item: item["time"])


def save_events(events):
    serialised = []
    for event in events:
        item = dict(event)
        if isinstance(item.get("time"), dt.datetime):
            item["time"] = item["time"].isoformat(timespec="seconds")
        serialised.append(item)
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        EVENTS_PATH.write_text(json.dumps(serialised, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_bundled_uk_foods():
    try:
        payload = json.loads(UK_COFID_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    items = payload.get("foods", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    foods = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        try:
            carbs = float(item.get("carbs_g"))
        except (TypeError, ValueError):
            continue
        if name and carbs >= 0:
            foods.append({
                "name": name,
                "serving": str(item.get("serving") or "100 g"),
                "carbs_g": carbs,
                "source": str(item.get("source") or "UK CoFID 2021"),
                "cofid_code": str(item.get("cofid_code") or ""),
            })
    return sorted(foods, key=lambda item: item["name"].casefold())


def find_food_matches(foods, query, limit=40):
    """Return a short, useful autocomplete list for the food-entry dialog."""
    query = str(query or "").strip().casefold()
    if not query:
        return list(foods)
    matches = [food for food in foods if query in str(food.get("name") or "").casefold()]
    return sorted(
        matches,
        key=lambda food: (
            0 if str(food.get("name") or "").casefold().startswith(query) else 1,
            str(food.get("name") or "").casefold(),
        ),
    )[:limit]


def load_foods():
    try:
        data = json.loads(FOODS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        data = None
    if data is None:
        bundled = load_bundled_uk_foods()
        if bundled:
            return bundled
        return sorted((dict(food) for food in COMMON_FOODS), key=lambda item: item["name"].casefold())
    foods = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            serving = str(item.get("serving") or "").strip()
            try:
                carbs = float(item.get("carbs_g"))
            except (TypeError, ValueError):
                continue
            if name and serving and carbs >= 0:
                foods.append({"name": name, "serving": serving, "carbs_g": carbs})
    return sorted(foods, key=lambda item: item["name"].casefold())


def save_foods(foods):
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        FOODS_PATH.write_text(json.dumps(foods, indent=2), encoding="utf-8")
    except OSError:
        pass


def export_recording_data(path, readings, events):
    """Export readings and user-entered events without any connection secrets."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        payload = {
            "readings": [
                {
                    "time": item["time"].isoformat(timespec="seconds"),
                    "glucose_mgdl": round(float(item["mgdl"]), 2),
                    "glucose_mmol_l": round(float(display_value(item["mgdl"], "mmol/L")), 2),
                    "trend": item.get("trend", ""),
                }
                for item in readings
            ],
            "events": [
                {
                    key: value.isoformat(timespec="seconds") if isinstance(value, dt.datetime) else value
                    for key, value in event.items()
                    if key != "id"
                }
                for event in events
            ],
            "notice": "Recording export only. It does not calculate or recommend insulin doses.",
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return

    columns = [
        "record_type", "timestamp", "glucose_mgdl", "glucose_mmol_l", "trend",
        "food_description", "food_serving", "carbohydrates_g", "insulin_type", "insulin_units", "note",
    ]
    rows = []
    for item in readings:
        rows.append({
            "record_type": "reading",
            "timestamp": item["time"].isoformat(timespec="seconds"),
            "glucose_mgdl": round(float(item["mgdl"]), 2),
            "glucose_mmol_l": round(float(display_value(item["mgdl"], "mmol/L")), 2),
            "trend": item.get("trend", ""),
        })
    for event in events:
        row = {
            "record_type": event["type"],
            "timestamp": event["time"].isoformat(timespec="seconds"),
            "food_description": event.get("description", ""),
            "food_serving": event.get("serving", ""),
            "carbohydrates_g": event.get("carbs_g", ""),
            "insulin_type": event.get("insulin_type", ""),
            "insulin_units": event.get("insulin_units", ""),
            "note": event.get("note", ""),
        }
        rows.append(row)
    rows.sort(key=lambda row: row["timestamp"])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def credential_vault_available():
    try:
        import keyring
        backend = keyring.get_keyring()
        return (
            os.name == "nt"
            and type(backend).__module__ == "keyring.backends.Windows"
            and type(backend).__name__ == "WinVaultKeyring"
        )
    except Exception:
        return False


def get_vault_password(credential_key):
    if not credential_key or not credential_vault_available():
        return None
    try:
        import keyring
        return keyring.get_password(CREDENTIAL_SERVICE, credential_key)
    except Exception:
        return None


def set_vault_password(credential_key, secret):
    if not credential_vault_available():
        return False
    try:
        import keyring
        keyring.set_password(CREDENTIAL_SERVICE, credential_key, secret)
        return True
    except Exception:
        return False


def delete_vault_password(credential_key):
    if not credential_vault_available():
        return
    try:
        import keyring
        keyring.delete_password(CREDENTIAL_SERVICE, credential_key)
    except Exception:
        pass


class LibreViewOverlay:
    def __init__(self, root):
        self.root = root
        self.root.title("LibreView Desktop Overlay")
        self.root.geometry("1000x680")
        self.root.minsize(780, 520)
        self.root.configure(bg="#0b1220")

        self.settings = load_settings()
        self.events = load_events()
        self.foods = load_foods()
        self.readings = []
        self.csv_path = None
        self.last_modified = None
        self.data_source = None
        self.cloud_session = None
        self.live_provider_name = self.settings.get("live_provider", "Juggluco")
        self.cloud_busy = False
        self.provider_generation = 0
        self.worker_results = queue.Queue()
        self.login_window = None
        self.event_window = None
        self.overlay = None
        self.overlay_text = None
        self.overlay_labels = {}
        self.overlay_value_row = None
        self.overlay_close_button = None
        self.overlay_minimize_button = None
        self.overlay_text_transparent = False
        self.graph_tooltip = None
        self.overlay_x = int(self.settings.get("overlay_x", 30))
        self.overlay_y = int(self.settings.get("overlay_y", 30))
        self.tray_icon = None
        self.tray_thread = None
        self._click_through_procs = {}
        self.exiting = False
        self.update_busy = False
        self.last_update_check = None
        self.last_cloud_attempt = None
        self.last_successful_refresh = None
        self.last_connection_error = None
        self.cloud_refresh_job = None
        self.file_refresh_job = None
        self.drag_x = 0
        self.drag_y = 0

        self.always_on_top = tk.BooleanVar(value=True)
        self.always_on_top.set(bool(self.settings.get("always_on_top", True)))
        self.start_overlay = tk.BooleanVar(value=bool(self.settings.get("start_overlay", False)))
        self.overlay_enabled = tk.BooleanVar(value=self.start_overlay.get())
        self.overlay_color = tk.StringVar(value=self.settings.get("overlay_color", "Navy"))
        self.overlay_background_opacity = tk.IntVar(value=int(self.settings.get("overlay_background_opacity", 82)))
        self.overlay_number_opacity = tk.IntVar(value=int(self.settings.get("overlay_number_opacity", 100)))
        self.overlay_size = tk.StringVar(value=self.settings.get("overlay_size", "Medium"))
        self.overlay_locked = tk.BooleanVar(value=bool(self.settings.get("overlay_locked", False)))
        self.start_hidden = tk.BooleanVar(value=bool(self.settings.get("start_hidden", False)))
        self.start_with_windows = tk.BooleanVar(value=bool(self.settings.get("start_with_windows", False)))
        self.unit = tk.StringVar(value=self.settings.get("unit", "mmol/L"))
        self.refresh_interval = tk.IntVar(value=int(self.settings.get("refresh_interval", 60)))
        self.auto_check_updates = tk.BooleanVar(value=bool(self.settings.get("auto_check_updates", True)))
        self.status = tk.StringVar(value="Connect Juggluco locally for near-live readings, or open a CSV.")
        self.diagnostics = tk.StringVar(value="Last reading: none • Last connection attempt: none")

        self.build_main_ui()
        if self.start_with_windows.get():
            set_windows_startup(True)
        self.unit.trace_add("write", self.on_unit_change)
        self.overlay_color.trace_add("write", self.on_overlay_style_change)
        self.overlay_background_opacity.trace_add("write", self.on_overlay_style_change)
        self.overlay_number_opacity.trace_add("write", self.on_overlay_style_change)
        self.overlay_size.trace_add("write", self.on_overlay_size_change)
        self.root.after(50, self.schedule_refresh_jobs)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_main)
        self.root.bind("<Unmap>", self.handle_root_unmap, add="+")
        self.root.after(100, self.start_tray_icon)
        self.root.after(100, self.process_worker_results)
        self.root.after(30_000, self.refresh_freshness)
        self.root.after(500, self.try_auto_connect)
        self.root.after(3_000, self.auto_check_for_updates)
        if self.start_overlay.get():
            self.overlay_enabled.set(True)
            self.show_overlay()
            # Tk can create the Toplevels before Windows has mapped them. Reapply
            # the z-order after the first paint so startup matches the checkbox.
            self.root.after_idle(self.update_overlay_topmost)
            self.root.after(500, self.update_overlay_topmost)
        if self.start_hidden.get():
            self.root.after(250, self.minimize_main)

    def build_main_ui(self):
        viewport = tk.Frame(self.root, bg="#0b1220")
        viewport.pack(fill="both", expand=True)
        self.main_canvas = tk.Canvas(viewport, bg="#0b1220", highlightthickness=0)
        main_scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self.main_canvas.yview)
        main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_canvas.configure(yscrollcommand=main_scrollbar.set)
        content = tk.Frame(self.main_canvas, bg="#0b1220")
        content_window = self.main_canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda event: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>", lambda event: self.main_canvas.itemconfigure(content_window, width=event.width))
        self.main_canvas.bind_all("<MouseWheel>", self.on_main_mousewheel, add="+")

        header = tk.Frame(content, bg="#0b1220")
        header.pack(fill="x", padx=24, pady=(22, 10))
        tk.Label(header, text="Libre Desktop", fg="#f8fafc", bg="#0b1220", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(header, text="Near-live Libre display — local Juggluco recommended, Gluroo optional", fg="#94a3b8", bg="#0b1220", font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 0))

        controls = tk.Frame(content, bg="#111827")
        controls.pack(fill="x", padx=24, pady=(4, 8))
        self.live_button = tk.Button(controls, text="Connect Juggluco", command=self.open_juggluco_login, bg="#0f766e", fg="white", activebackground="#115e59", relief="flat", padx=14, pady=8)
        self.live_button.pack(side="left", padx=(12, 6), pady=12)
        self.live_source = tk.StringVar(value=LIVE_SOURCE_LABELS.get(self.live_provider_name, "Juggluco — Local"))
        tk.Label(controls, text="Live source:", fg="#94a3b8", bg="#111827").pack(side="left", padx=(12, 4))
        source_box = ttk.Combobox(controls, textvariable=self.live_source, values=[*LIVE_SOURCE_LABELS.values(), CSV_SOURCE_LABEL], state="readonly", width=24)
        source_box.pack(side="left", padx=4)
        source_box.bind("<<ComboboxSelected>>", self.on_live_source_change)
        tk.Button(controls, text="Open CSV", command=self.choose_file, bg="#475569", fg="white", activebackground="#334155", relief="flat", padx=14, pady=8).pack(side="left", padx=6, pady=12)
        tk.Button(controls, text="Show overlay", command=self.enable_overlay, bg="#16a34a", fg="white", activebackground="#15803d", relief="flat", padx=14, pady=8).pack(side="left", padx=6, pady=12)
        self.update_button = tk.Button(controls, text="Update app", command=self.check_for_updates, bg="#0891b2", fg="white", activebackground="#0e7490", relief="flat", padx=14, pady=8)
        self.update_button.pack(side="left", padx=6, pady=12)
        tk.Checkbutton(controls, text="Always on top", variable=self.always_on_top, command=self.toggle_always_on_top, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=12)
        tk.Checkbutton(controls, text="Lock overlay", variable=self.overlay_locked, command=self.toggle_overlay_lock, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=8)
        tk.Button(controls, text="Exit", command=self.exit_application, bg="#7f1d1d", fg="white", activebackground="#991b1b", relief="flat", padx=12, pady=8).pack(side="right", padx=8, pady=12)
        unit_box = ttk.Combobox(controls, textvariable=self.unit, values=["mmol/L", "mg/dL"], state="readonly", width=8)
        unit_box.pack(side="right", padx=14)
        tk.Label(controls, text="Units", fg="#94a3b8", bg="#111827").pack(side="right")

        style_bar = tk.Frame(content, bg="#111827")
        style_bar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(style_bar, text="Overlay colour", fg="#94a3b8", bg="#111827").pack(side="left", padx=(14, 6), pady=8)
        ttk.Combobox(style_bar, textvariable=self.overlay_color, values=["Navy", "Black", "Purple", "Forest", "Slate"], state="readonly", width=10).pack(side="left", pady=8)
        tk.Label(style_bar, text="Background", fg="#94a3b8", bg="#111827").pack(side="left", padx=(20, 6), pady=8)
        tk.Scale(style_bar, from_=35, to=100, orient="horizontal", variable=self.overlay_background_opacity, showvalue=True, length=105, bg="#111827", fg="#e5e7eb", troughcolor="#334155", highlightthickness=0, activebackground="#38bdf8").pack(side="left", pady=2)
        tk.Label(style_bar, text="Number", fg="#94a3b8", bg="#111827").pack(side="left", padx=(12, 6), pady=8)
        tk.Scale(style_bar, from_=35, to=100, orient="horizontal", variable=self.overlay_number_opacity, showvalue=True, length=105, bg="#111827", fg="#e5e7eb", troughcolor="#334155", highlightthickness=0, activebackground="#38bdf8").pack(side="left", pady=2)
        tk.Label(style_bar, text="Size", fg="#94a3b8", bg="#111827").pack(side="left", padx=(20, 6), pady=8)
        ttk.Combobox(style_bar, textvariable=self.overlay_size, values=list(OVERLAY_SIZES), state="readonly", width=9).pack(side="left", pady=8)

        startup_bar = tk.Frame(content, bg="#111827")
        startup_bar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(startup_bar, text="Startup", fg="#94a3b8", bg="#111827").pack(side="left", padx=(14, 6), pady=8)
        tk.Checkbutton(startup_bar, text="Start with overlay", variable=self.start_overlay, command=self.toggle_start_overlay, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=8)
        tk.Checkbutton(startup_bar, text="Start hidden in tray", variable=self.start_hidden, command=self.toggle_start_hidden, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=8)
        tk.Checkbutton(startup_bar, text="Start with Windows", variable=self.start_with_windows, command=self.toggle_start_with_windows, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=8)

        event_bar = tk.Frame(content, bg="#111827")
        event_bar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(event_bar, text="Timeline", fg="#94a3b8", bg="#111827").pack(side="left", padx=(14, 10), pady=8)
        tk.Button(event_bar, text="Add food", command=lambda: self.open_event_dialog("food"), bg=EVENT_COLORS["food"], fg="white", activebackground="#a16207", relief="flat", padx=12, pady=6).pack(side="left", padx=5, pady=6)
        tk.Button(event_bar, text="Log insulin", command=lambda: self.open_event_dialog("insulin"), bg=EVENT_COLORS["insulin"], fg="white", activebackground="#b91c1c", relief="flat", padx=12, pady=6).pack(side="left", padx=5, pady=6)
        tk.Button(event_bar, text="Food database", command=self.open_food_database, bg="#2563eb", fg="white", activebackground="#1d4ed8", relief="flat", padx=12, pady=6).pack(side="left", padx=5, pady=6)
        tk.Label(event_bar, text="Record events only — no dose recommendations", fg="#94a3b8", bg="#111827", font=("Segoe UI", 8)).pack(side="left", padx=14)

        status_bar = tk.Frame(content, bg="#0b1220")
        status_bar.pack(fill="x", padx=28, pady=(0, 10))
        tk.Label(status_bar, textvariable=self.status, fg="#cbd5e1", bg="#0b1220", anchor="w", font=("Segoe UI", 9)).pack(fill="x")
        tk.Label(status_bar, textvariable=self.diagnostics, fg="#64748b", bg="#0b1220", anchor="w", font=("Segoe UI", 8)).pack(fill="x", pady=(3, 0))

        options_bar = tk.Frame(content, bg="#111827")
        options_bar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(options_bar, text="Refresh", fg="#94a3b8", bg="#111827").pack(side="left", padx=(14, 6), pady=8)
        refresh_box = ttk.Combobox(options_bar, textvariable=self.refresh_interval, values=list(REFRESH_INTERVAL_OPTIONS), state="readonly", width=8)
        refresh_box.pack(side="left", pady=8)
        tk.Label(options_bar, text="seconds", fg="#94a3b8", bg="#111827").pack(side="left", padx=(5, 12))
        refresh_box.bind("<<ComboboxSelected>>", self.on_refresh_interval_change)
        tk.Checkbutton(options_bar, text="Check for updates on startup", variable=self.auto_check_updates, command=self.toggle_auto_update_check, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=6)
        tk.Button(options_bar, text="Reset position", command=self.reset_overlay_position, bg="#475569", fg="white", activebackground="#334155", relief="flat", padx=10, pady=6).pack(side="right", padx=6, pady=6)
        tk.Button(options_bar, text="Export data", command=self.export_recordings, bg="#0f766e", fg="white", activebackground="#115e59", relief="flat", padx=10, pady=6).pack(side="right", padx=6, pady=6)
        tk.Button(options_bar, text="Manage events", command=self.open_event_log, bg="#475569", fg="white", activebackground="#334155", relief="flat", padx=10, pady=6).pack(side="right", padx=6, pady=6)
        tk.Button(options_bar, text="Import appearance", command=self.import_visual_settings, bg="#475569", fg="white", activebackground="#334155", relief="flat", padx=10, pady=6).pack(side="right", padx=6, pady=6)
        tk.Button(options_bar, text="Export appearance", command=self.export_visual_settings, bg="#475569", fg="white", activebackground="#334155", relief="flat", padx=10, pady=6).pack(side="right", padx=6, pady=6)
        tk.Button(options_bar, text="About", command=self.show_about, bg="#475569", fg="white", activebackground="#334155", relief="flat", padx=10, pady=6).pack(side="right", padx=6, pady=6)

        self.current_card = tk.Frame(content, bg="#172033")
        self.current_card.pack(fill="x", padx=24, pady=(0, 14))
        self.current_value = tk.Label(self.current_card, text="—", fg="#f8fafc", bg="#172033", font=("Segoe UI", 44, "bold"))
        self.current_value.pack(side="left", padx=(22, 4), pady=18)
        self.current_trend = tk.Label(self.current_card, text="", fg="#38bdf8", bg="#172033", font=("Segoe UI", 30, "bold"))
        self.current_trend.pack(side="left", padx=(0, 8))
        self.current_unit = tk.Label(self.current_card, text=self.unit.get(), fg="#94a3b8", bg="#172033", font=("Segoe UI", 13))
        self.current_unit.pack(side="left", pady=(26, 0))
        self.current_time = tk.Label(self.current_card, text="No data loaded", fg="#cbd5e1", bg="#172033", justify="right", font=("Segoe UI", 11))
        self.current_time.pack(side="right", padx=22)

        graph_frame = tk.Frame(content, bg="#111827", height=390)
        graph_frame.pack(fill="x", padx=24, pady=(0, 24))
        graph_frame.pack_propagate(False)
        tk.Label(graph_frame, text="Recent glucose history", fg="#f8fafc", bg="#111827", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        self.canvas = tk.Canvas(graph_frame, bg="#111827", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", lambda event: self.draw_graph())
        self.canvas.bind("<Leave>", lambda event: self.hide_graph_event_tooltip())

    def on_main_mousewheel(self, event):
        if getattr(self, "main_canvas", None) and self.main_canvas.winfo_exists():
            self.main_canvas.yview_scroll(-int(event.delta / 120), "units")

    def open_gluroo_login(self):
        if self.login_window and self.login_window.winfo_exists():
            self.login_window.destroy()
        self.login_window = tk.Toplevel(self.root)
        self.login_window.title("Connect Gluroo")
        self.login_window.geometry("500x350")
        self.login_window.resizable(False, False)
        self.login_window.configure(bg="#111827")
        self.login_window.transient(self.root)

        saved_url = get_vault_password("gluroo-global-connect")
        url_var = tk.StringVar(value=saved_url or "")
        vault_available = credential_vault_available()
        remember_var = tk.BooleanVar(value=bool(saved_url) and vault_available)
        show_var = tk.BooleanVar(value=False)

        tk.Label(self.login_window, text="Connect the Gluroo live feed", fg="#f8fafc", bg="#111827", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=24, pady=(22, 5))
        tk.Label(
            self.login_window,
            text=("In Gluroo, open Settings → Gluroo Global Connect Nightscout.\n"
                  "Paste the URL, token and header block here, or paste a complete link."),
            fg="#94a3b8", bg="#111827", justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 14))
        form = tk.Frame(self.login_window, bg="#111827")
        form.pack(fill="x", padx=24)
        tk.Label(form, text="Gluroo Global Connect URL", fg="#cbd5e1", bg="#111827").pack(anchor="w")
        url_entry = tk.Entry(form, textvariable=url_var, show="•", font=("Segoe UI", 11), relief="flat")
        url_entry.pack(fill="x", pady=(3, 8), ipady=5)

        def toggle_show():
            url_entry.config(show="" if show_var.get() else "•")

        tk.Checkbutton(form, text="Show URL", variable=show_var, command=toggle_show, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(anchor="w")
        remember_text = "Remember securely in Windows Credential Manager" if vault_available else "Secure Windows credential storage is unavailable"
        remember_box = tk.Checkbutton(form, text=remember_text, variable=remember_var, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb")
        remember_box.pack(anchor="w")
        if not vault_available:
            remember_box.config(state="disabled")

        buttons = tk.Frame(self.login_window, bg="#111827")
        buttons.pack(fill="x", padx=24, pady=16)
        connect_button = tk.Button(buttons, text="Connect", bg="#7c3aed", fg="white", relief="flat", padx=18, pady=8)
        connect_button.pack(side="left")
        tk.Button(buttons, text="Open Gluroo web app", command=lambda: webbrowser.open("https://app.gluroo.com/"), bg="#334155", fg="white", relief="flat", padx=12, pady=8).pack(side="right")

        def submit(event=None):
            global_connect_url = url_var.get().strip()
            if not global_connect_url:
                messagebox.showwarning("Missing details", "Paste the Gluroo URL/token/header details.", parent=self.login_window)
                return
            url_var.set("")
            connect_button.config(state="disabled", text="Connecting…")
            url_entry.config(state="disabled")
            self.start_gluroo_connection(global_connect_url, remember_var.get(), self.login_window)

        connect_button.config(command=submit)
        url_entry.bind("<Return>", submit)
        url_entry.focus_set()

    def open_juggluco_login(self):
        if self.login_window and self.login_window.winfo_exists():
            self.login_window.destroy()
        self.login_window = tk.Toplevel(self.root)
        self.login_window.title("Connect Juggluco")
        self.login_window.geometry("540x470")
        self.login_window.resizable(False, False)
        self.login_window.configure(bg="#111827")
        self.login_window.transient(self.root)
        host_var = tk.StringVar(value=self.settings.get("juggluco_host", ""))
        port_var = tk.StringVar(value=str(self.settings.get("juggluco_port", 17580)))
        secret_var = tk.StringVar(value=get_vault_password("juggluco-api-secret") or "")
        remember_var = tk.BooleanVar(value=bool(self.settings.get("juggluco_remember")) and credential_vault_available())
        show_var = tk.BooleanVar(value=False)
        tk.Label(self.login_window, text="Connect Juggluco", fg="#f8fafc", bg="#111827", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=24, pady=(22, 5))
        tk.Label(self.login_window, text=("Juggluco receives your Libre readings directly from the sensor over Bluetooth.\n"
            "Libre Desktop Overlay connects to Juggluco over your local network."), fg="#94a3b8", bg="#111827", justify="left").pack(anchor="w", padx=24, pady=(0, 12))
        form = tk.Frame(self.login_window, bg="#111827")
        form.pack(fill="x", padx=24)
        for label, variable, show in (("Phone IP / hostname", host_var, ""), ("Port", port_var, ""), ("API secret (optional)", secret_var, "•")):
            tk.Label(form, text=label, fg="#cbd5e1", bg="#111827").pack(anchor="w")
            entry = tk.Entry(form, textvariable=variable, show=show, font=("Segoe UI", 11), relief="flat")
            entry.pack(fill="x", pady=(3, 8), ipady=4)
            if label.startswith("API"):
                secret_entry = entry
        def toggle_show():
            secret_entry.config(show="" if show_var.get() else "•")
        tk.Checkbutton(form, text="Show secret", variable=show_var, command=toggle_show, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(anchor="w")
        remember_box = tk.Checkbutton(form, text="Remember securely in Windows Credential Manager", variable=remember_var, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb")
        remember_box.pack(anchor="w")
        if not credential_vault_available():
            remember_box.config(state="disabled", text="Secure Windows credential storage is unavailable")
        tk.Label(self.login_window, text=("Juggluco: Settings → Exchange data → Web server. Enable it, unset Local only,\n"
            "use port 17580, and keep the phone and PC on the same local network.\n"
            "A secret is strongly recommended. Do not port-forward this server to the internet."), fg="#94a3b8", bg="#111827", justify="left", wraplength=490).pack(anchor="w", padx=24, pady=12)
        buttons = tk.Frame(self.login_window, bg="#111827")
        buttons.pack(fill="x", padx=24, pady=6)
        test_button = tk.Button(buttons, text="Test connection", bg="#334155", fg="white", relief="flat", padx=12, pady=8)
        test_button.pack(side="left")
        connect_button = tk.Button(buttons, text="Connect", bg="#0f766e", fg="white", relief="flat", padx=18, pady=8)
        connect_button.pack(side="left", padx=8)
        def start(connect):
            try:
                port = int(port_var.get() or 17580)
                session = JugglucoSession.connect(host_var.get(), port, secret_var.get())
            except (CloudSetupError, ValueError) as error:
                messagebox.showerror("Juggluco connection failed", str(error), parent=self.login_window)
                return
            if not connect:
                test_button.config(state="disabled", text="Testing…")
                def worker():
                    try:
                        readings = session.fetch()
                        self.worker_results.put(("juggluco_test", readings, test_button))
                    except (CloudLoginError, CloudSetupError) as error:
                        self.worker_results.put(("juggluco_test_error", str(error), test_button))
                threading.Thread(target=worker, daemon=True).start()
                return
            self.settings.update({"live_provider": "Juggluco", "juggluco_host": host_var.get().strip(), "juggluco_port": port})
            self.start_juggluco_connection(session, secret_var.get(), remember_var.get(), self.login_window)
        test_button.config(command=lambda: start(False))
        connect_button.config(command=lambda: start(True))

    def on_live_source_change(self, event=None):
        if self.live_source.get() == CSV_SOURCE_LABEL:
            self.live_source.set(LIVE_SOURCE_LABELS.get(self.live_provider_name, "Juggluco — Local"))
            self.choose_file()
            return
        self.live_provider_name = next((provider for provider, label in LIVE_SOURCE_LABELS.items() if label == self.live_source.get()), "Juggluco")
        self.settings["live_provider"] = self.live_provider_name
        save_settings(self.settings)
        self.provider_generation += 1
        self.cloud_session = None
        self.cloud_busy = False
        self.data_source = None
        self.readings = []
        if self.live_provider_name == "Juggluco":
            self.live_button.config(text="Connect Juggluco", command=self.open_juggluco_login)
        else:
            self.live_button.config(text="Connect Gluroo", command=self.open_gluroo_login)
        self.status.set(f"{self.live_provider_name} selected. Connect to start live readings.")
        self.update_diagnostics()
        self.update_display()

    def try_auto_connect(self):
        if self.settings.get("live_provider") == "Juggluco" and self.settings.get("juggluco_remember") and self.settings.get("juggluco_host"):
            secret = get_vault_password("juggluco-api-secret")
            try:
                session = JugglucoSession.connect(self.settings["juggluco_host"], self.settings.get("juggluco_port", 17580), secret)
                self.start_juggluco_connection(session, secret or "", True, None)
            except CloudSetupError:
                pass
        elif self.settings.get("gluroo_remember"):
            global_connect_url = get_vault_password("gluroo-global-connect")
            if global_connect_url:
                self.start_gluroo_connection(global_connect_url, True, None)

    def start_gluroo_connection(self, global_connect_url, remember, login_window):
        self.provider_generation += 1
        generation = self.provider_generation
        self.cloud_busy = True
        self.last_cloud_attempt = dt.datetime.now()
        self.last_connection_error = None
        self.live_button.config(state="disabled", text="Connecting…")
        self.status.set("Connecting to the Gluroo live feed…")
        self.update_diagnostics()

        def worker():
            try:
                session = GlurooSession.connect(global_connect_url)
                cloud_readings = session.fetch()
                if generation != self.provider_generation:
                    return
                if remember:
                    saved_ok = set_vault_password("gluroo-global-connect", global_connect_url)
                else:
                    delete_vault_password("gluroo-global-connect")
                    saved_ok = True
                self.worker_results.put(("connected", generation, session, cloud_readings, "Gluroo", remember, saved_ok, login_window))
            except (CloudLoginError, CloudSetupError) as error:
                self.worker_results.put(("connect_error", generation, str(error), login_window))
            except Exception:
                self.worker_results.put(("connect_error", generation, "An unexpected Gluroo connection error occurred.", login_window))

        threading.Thread(target=worker, daemon=True).start()

    def process_worker_results(self):
        try:
            while True:
                result = self.worker_results.get_nowait()
                kind = result[0]
                if kind == "update_checked":
                    self.last_update_check = result[1]
                    self.update_diagnostics()
                elif kind == "connected":
                    _, generation, session, cloud_readings, provider, remember, saved_ok, login_window = result
                    if generation != self.provider_generation:
                        continue
                    self.cloud_busy = False
                    self.cloud_session = session
                    self.data_source = "cloud"
                    self.live_provider_name = provider
                    self.live_source.set(LIVE_SOURCE_LABELS[provider])
                    self.last_successful_refresh = dt.datetime.now()
                    self.last_connection_error = None
                    self.readings = [
                        {"time": item.time, "mgdl": item.mgdl, "trend": item.trend}
                        for item in cloud_readings
                    ]
                    self.settings.update({"unit": self.unit.get(), "live_provider": provider})
                    if provider == "Gluroo":
                        self.settings["gluroo_remember"] = remember and saved_ok
                    else:
                        self.settings["juggluco_remember"] = remember and saved_ok
                    save_settings(self.settings)
                    if login_window and login_window.winfo_exists():
                        login_window.destroy()
                    self.live_button.config(state="normal", text=f"Reconnect {provider}")
                    suffix = " • secure auto-connect unavailable" if remember and not saved_ok else ""
                    self.status.set(f"Near-live via {provider} • {'local' if provider == 'Juggluco' else 'cloud'} • checked {dt.datetime.now():%H:%M:%S}{suffix}")
                    self.update_diagnostics()
                    self.update_display()
                    if self.overlay_enabled.get() or login_window or self.start_overlay.get():
                        self.enable_overlay()
                elif kind == "connect_error":
                    _, generation, error_message, login_window = result
                    if generation != self.provider_generation:
                        continue
                    self.cloud_busy = False
                    self.live_button.config(state="normal", text=f"Connect {self.live_provider_name}")
                    self.last_connection_error = error_message
                    self.status.set(error_message)
                    self.update_diagnostics()
                    if login_window and login_window.winfo_exists():
                        login_window.destroy()
                    messagebox.showerror(f"{self.live_provider_name} connection failed", error_message, parent=self.root)
                elif kind == "juggluco_test":
                    _, readings, button = result
                    button.config(state="normal", text="Test connection")
                    latest = readings[-1]
                    age = max(0, int((dt.datetime.now() - latest.time).total_seconds()))
                    messagebox.showinfo("Juggluco connection successful", f"Latest glucose: {format_glucose(latest.mgdl, self.unit.get())} {self.unit.get()} {latest.trend}\nReading time: {latest.time:%H:%M}\nReading age: {age} seconds\nHistory received: {len(readings)} readings", parent=self.login_window or self.root)
                elif kind == "juggluco_test_error":
                    _, error_message, button = result
                    button.config(state="normal", text="Test connection")
                    messagebox.showerror("Juggluco connection failed", error_message, parent=self.login_window or self.root)
                elif kind == "refreshed":
                    _, generation, cloud_readings = result
                    if generation != self.provider_generation or self.data_source != "cloud":
                        continue
                    self.cloud_busy = False
                    self.last_successful_refresh = dt.datetime.now()
                    self.last_connection_error = None
                    self.readings = [
                        {"time": item.time, "mgdl": item.mgdl, "trend": item.trend}
                        for item in cloud_readings
                    ]
                    provider = self.live_provider_name
                    self.status.set(f"Near-live via {provider} • {'local' if provider == 'Juggluco' else 'cloud'} • checked {dt.datetime.now():%H:%M:%S}")
                    self.update_diagnostics()
                    self.update_display()
                elif kind == "refresh_error":
                    _, generation, error_message = result
                    if generation != self.provider_generation or self.data_source != "cloud":
                        continue
                    self.cloud_busy = False
                    self.last_connection_error = error_message
                    self.status.set(f"Refresh failed; keeping last reading • {error_message}")
                    self.update_diagnostics()
                    self.update_display()
                elif kind == "update_up_to_date":
                    _, silent = result
                    self.update_busy = False
                    self.update_button.config(state="normal", text="Update app")
                    if not silent:
                        self.status.set(f"Libre Desktop Overlay {APP_VERSION} is up to date.")
                    self.update_diagnostics()
                elif kind == "update_available":
                    _, latest_version, asset_url, silent = result
                    self.update_busy = False
                    self.update_button.config(state="normal", text="Update app")
                    install = messagebox.askyesno(
                        "Update available",
                        f"Version {latest_version} is available. Download and install it now?",
                        parent=self.root,
                    )
                    if install:
                        self.download_update(asset_url, latest_version)
                elif kind == "update_error":
                    _, error_message, silent = result
                    self.update_busy = False
                    self.update_button.config(state="normal", text="Update app")
                    if not silent:
                        self.status.set(error_message)
                        messagebox.showwarning("Update check", error_message, parent=self.root)
                elif kind == "update_downloaded":
                    _, installer_path = result
                    self.update_busy = False
                    self.update_button.config(state="normal", text="Update app")
                    try:
                        if not self.launch_installer_and_restart(installer_path):
                            raise OSError("Could not start the update helper.")
                    except OSError:
                        self.status.set("The downloaded update could not be started.")
                        messagebox.showerror("Update failed", "The downloaded installer could not be started.", parent=self.root)
                        continue
                    self.exit_application()
                elif kind == "update_download_error":
                    _, error_message = result
                    self.update_busy = False
                    self.update_button.config(state="normal", text="Update app")
                    self.status.set(error_message)
                    messagebox.showerror("Update failed", error_message, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.process_worker_results)

    def schedule_refresh_jobs(self):
        interval_ms = int(self.refresh_interval.get()) * 1000
        if self.file_refresh_job:
            self.root.after_cancel(self.file_refresh_job)
        if self.cloud_refresh_job:
            self.root.after_cancel(self.cloud_refresh_job)
        self.file_refresh_job = self.root.after(interval_ms, self.poll_file)
        self.cloud_refresh_job = self.root.after(interval_ms, self.poll_cloud)

    def on_refresh_interval_change(self, event=None):
        try:
            interval = int(self.refresh_interval.get())
        except (TypeError, ValueError):
            interval = 60
            self.refresh_interval.set(interval)
        if interval not in REFRESH_INTERVAL_OPTIONS:
            interval = 60
            self.refresh_interval.set(interval)
        self.settings["refresh_interval"] = interval
        save_settings(self.settings)
        self.schedule_refresh_jobs()
        self.status.set(f"Refresh interval set to {interval} seconds.")

    def toggle_auto_update_check(self):
        self.settings["auto_check_updates"] = self.auto_check_updates.get()
        save_settings(self.settings)

    def update_diagnostics(self):
        reading_text = "none"
        if self.readings:
            reading_text = self.readings[-1]["time"].strftime("%H:%M:%S")
        attempt_text = self.last_cloud_attempt.strftime("%H:%M:%S") if self.last_cloud_attempt else "none"
        success_text = self.last_successful_refresh.strftime("%H:%M:%S") if self.last_successful_refresh else "none"
        update_text = self.last_update_check.strftime("%H:%M:%S") if self.last_update_check else "none"
        error_text = f" • Error: {self.last_connection_error}" if self.last_connection_error else ""
        provider_text = f"{self.live_provider_name} {'Local' if self.live_provider_name == 'Juggluco' else 'Cloud'}"
        self.diagnostics.set(
            f"Provider: {provider_text} • Last reading: {reading_text} • Last successful refresh: {success_text} • "
            f"Last connection attempt: {attempt_text} • Last update check: {update_text}{error_text}"
        )

    def poll_cloud(self):
        self.cloud_refresh_job = None
        self.last_cloud_attempt = dt.datetime.now() if self.cloud_session else self.last_cloud_attempt
        self.update_diagnostics()
        if self.cloud_session and self.data_source == "cloud" and not self.cloud_busy:
            self.cloud_busy = True
            generation = self.provider_generation
            session = self.cloud_session

            def worker():
                try:
                    self.worker_results.put(("refreshed", generation, session.fetch()))
                except Exception as error:
                    message = str(error) if isinstance(error, (CloudLoginError, CloudSetupError)) else "Unexpected refresh error."
                    self.worker_results.put(("refresh_error", generation, message))

            threading.Thread(target=worker, daemon=True).start()
        self.cloud_refresh_job = self.root.after(int(self.refresh_interval.get()) * 1000, self.poll_cloud)

    def choose_file(self):
        path = filedialog.askopenfilename(title="Select LibreView CSV export", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.load_file(path)

    def open_event_dialog(self, event_type, event=None, on_saved=None):
        if self.event_window and self.event_window.winfo_exists():
            self.event_window.destroy()
        is_food = event_type == "food"
        editing = event is not None
        event_to_edit = dict(event or {})
        self.event_window = tk.Toplevel(self.root)
        self.event_window.title(("Edit food" if is_food else "Edit insulin") if editing else ("Add food" if is_food else "Log insulin"))
        self.event_window.geometry("480x450" if is_food else "480x410")
        self.event_window.resizable(False, False)
        self.event_window.configure(bg="#111827")
        self.event_window.transient(self.root)
        self.event_window.grab_set()

        title = (("Edit food event" if is_food else "Edit insulin event") if editing else ("Record food eaten" if is_food else "Record insulin injection"))
        tk.Label(self.event_window, text=title, fg="#f8fafc", bg="#111827", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=24, pady=(22, 4))
        tk.Label(
            self.event_window,
            text=("This records an event for the graph and export only. It does not calculate or recommend a dose."),
            fg="#94a3b8", bg="#111827", wraplength=420, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 14))

        form = tk.Frame(self.event_window, bg="#111827")
        form.pack(fill="x", padx=24)
        event_time = event_to_edit.get("time")
        time_var = tk.StringVar(value=(event_time.strftime("%Y-%m-%d %H:%M") if isinstance(event_time, dt.datetime) else dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
        first_var = tk.StringVar(value=(event_to_edit.get("description", "") if is_food else event_to_edit.get("insulin_type", "Rapid-acting")))
        serving_var = tk.StringVar(value=event_to_edit.get("serving", "") if is_food else "")
        existing_amount = event_to_edit.get("carbs_g" if is_food else "insulin_units")
        amount_var = tk.StringVar(value=f"{existing_amount:g}" if isinstance(existing_amount, (int, float)) else "")

        def add_entry(label, variable, row, width=42):
            tk.Label(form, text=label, fg="#cbd5e1", bg="#111827").grid(row=row, column=0, sticky="w", pady=(0, 3))
            entry = tk.Entry(form, textvariable=variable, width=width, relief="flat", font=("Segoe UI", 10))
            entry.grid(row=row, column=1, sticky="ew", pady=(0, 8), ipady=4)
            return entry

        if is_food:
            food_box = ttk.Combobox(form, textvariable=first_var, values=[food["name"] for food in self.foods], width=39)
            tk.Label(form, text="Food/group", fg="#cbd5e1", bg="#111827").grid(row=0, column=0, sticky="w", pady=(0, 3))
            food_box.grid(row=0, column=1, sticky="ew", pady=(0, 8), ipady=2)

            def apply_food(food):
                nonlocal auto_scale_base_serving, auto_scale_base_carbs
                first_var.set(food["name"])
                auto_scale_base_serving = food["serving"]
                auto_scale_base_carbs = food["carbs_g"]
                amount_var.set(f"{food['carbs_g']:g}")
                serving_var.set(food["serving"])
                update_carbs_from_serving()

            suggestion_popup = None
            suggestion_list = None
            suggestion_items = []

            def close_food_suggestions(event=None):
                nonlocal suggestion_popup, suggestion_list
                if suggestion_popup and suggestion_popup.winfo_exists():
                    suggestion_popup.destroy()
                suggestion_popup = None
                suggestion_list = None

            def choose_food_suggestion(event):
                if not suggestion_list:
                    return
                index = suggestion_list.nearest(event.y)
                if 0 <= index < len(suggestion_items):
                    apply_food(suggestion_items[index])
                    close_food_suggestions()
                    food_box.focus_set()

            def select_food(event=None):
                typed = first_var.get().strip().casefold()
                exact = next((food for food in self.foods if food["name"].casefold() == typed), None)
                if exact:
                    apply_food(exact)
                    close_food_suggestions()

            def update_food_suggestions(event=None):
                nonlocal suggestion_popup, suggestion_list
                matches = find_food_matches(self.foods, first_var.get())
                suggestion_items.clear()
                suggestion_items.extend(matches)
                food_box["values"] = [food["name"] for food in matches]
                if not matches or not first_var.get().strip():
                    close_food_suggestions()
                    food_box.focus_set()
                    return
                if suggestion_popup is None or not suggestion_popup.winfo_exists():
                    suggestion_popup = tk.Toplevel(self.event_window)
                    suggestion_popup.overrideredirect(True)
                    suggestion_popup.configure(bg="#334155")
                    suggestion_popup.wm_attributes("-topmost", True)
                    try:
                        suggestion_popup.focusmodel("passive")
                    except tk.TclError:
                        pass
                    suggestion_list = tk.Listbox(
                        suggestion_popup,
                        bg="#1e293b",
                        fg="#f8fafc",
                        selectbackground=EVENT_COLORS["food"],
                        selectforeground="#ffffff",
                        relief="flat",
                        highlightthickness=0,
                        activestyle="none",
                        font=("Segoe UI", 9),
                    )
                    suggestion_list.pack(fill="both", expand=True, padx=1, pady=1)
                    suggestion_list.bind("<ButtonRelease-1>", choose_food_suggestion)
                suggestion_list.delete(0, "end")
                for food in matches:
                    suggestion_list.insert("end", food["name"])
                suggestion_list.configure(height=min(len(matches), 8))
                suggestion_popup.update_idletasks()
                x = food_box.winfo_rootx()
                y = food_box.winfo_rooty() + food_box.winfo_height()
                suggestion_popup.geometry(f"{food_box.winfo_width()}x{suggestion_list.winfo_reqheight()}+{x}+{y}")
                food_box.focus_set()

            food_box.bind("<<ComboboxSelected>>", select_food)
            food_box.bind("<KeyRelease>", update_food_suggestions)
            auto_scale_base_serving = event_to_edit.get("serving", "")
            auto_scale_base_carbs = existing_amount

            def update_carbs_from_serving(*_):
                scaled = scale_carbs_for_gram_serving(
                    serving_var.get(), auto_scale_base_serving, auto_scale_base_carbs
                )
                if scaled is not None:
                    amount_var.set(f"{scaled:g}")

            serving_var.trace_add("write", update_carbs_from_serving)
            serving_entry = add_entry("Serving/portion", serving_var, 1)
            serving_entry.bind("<KeyRelease>", update_carbs_from_serving)
            serving_entry.bind("<FocusOut>", update_carbs_from_serving)
            add_entry("Carbohydrates (g, editable)", amount_var, 2)
            tk.Label(form, text=f"Estimates: {FOOD_REFERENCE_SOURCE}. Check labels and adjust.", fg="#94a3b8", bg="#111827", wraplength=280, justify="left", font=("Segoe UI", 8)).grid(row=3, column=1, sticky="w", pady=(0, 8))

            def add_food_to_database():
                nonlocal auto_scale_base_serving, auto_scale_base_carbs
                name = first_var.get().strip()
                serving = serving_var.get().strip()
                try:
                    carbs = float(amount_var.get().strip())
                except ValueError:
                    carbs = -1
                if not name or not serving or carbs < 0:
                    messagebox.showerror(
                        "Food details required",
                        "Enter a food name, serving/portion, and non-negative carbohydrate amount before adding it to the list.",
                        parent=self.event_window,
                    )
                    return
                duplicate = next((food for food in self.foods if food["name"].casefold() == name.casefold()), None)
                if duplicate:
                    messagebox.showinfo(
                        "Food already listed",
                        f"{duplicate['name']} is already in the food list. You can edit it from Food database.",
                        parent=self.event_window,
                    )
                    return
                self.foods.append({"name": name, "serving": serving, "carbs_g": carbs})
                self.foods.sort(key=lambda item: item["name"].casefold())
                save_foods(self.foods)
                auto_scale_base_serving = serving
                auto_scale_base_carbs = carbs
                food_box["values"] = [food["name"] for food in find_food_matches(self.foods, name)]
                self.status.set(f"Added {name} to the food list.")
                messagebox.showinfo("Food added", f"{name} was added to the food list for future entries.", parent=self.event_window)
        else:
            tk.Label(form, text="Insulin type", fg="#cbd5e1", bg="#111827").grid(row=0, column=0, sticky="w", pady=(0, 3))
            insulin_box = ttk.Combobox(form, textvariable=first_var, values=INSULIN_TYPE_OPTIONS, width=39)
            insulin_box.grid(row=0, column=1, sticky="ew", pady=(0, 8), ipady=2)
            add_entry("Amount injected (units)", amount_var, 1)
        time_row = 4 if is_food else 2
        note_row = 5 if is_food else 3
        add_entry("Date and time", time_var, time_row)
        tk.Label(form, text="Notes (optional)", fg="#cbd5e1", bg="#111827").grid(row=note_row, column=0, sticky="nw", pady=(0, 3))
        note_box = tk.Text(form, height=4, width=40, relief="flat", font=("Segoe UI", 10))
        note_box.grid(row=note_row, column=1, sticky="ew", pady=(0, 8))
        if event_to_edit.get("note"):
            note_box.insert("1.0", event_to_edit["note"])
        form.columnconfigure(1, weight=1)

        buttons = tk.Frame(self.event_window, bg="#111827")
        buttons.pack(fill="x", padx=24, pady=12)

        def save_event():
            timestamp = parse_timestamp(time_var.get())
            if not timestamp:
                messagebox.showerror("Invalid time", "Enter the time as YYYY-MM-DD HH:MM.", parent=self.event_window)
                return
            note = note_box.get("1.0", "end").strip()
            saved_event = dict(event_to_edit) if editing else {"id": uuid.uuid4().hex, "type": event_type}
            saved_event.update({"type": event_type, "time": timestamp, "note": note})
            if is_food:
                description = first_var.get().strip()
                if not description:
                    messagebox.showerror("Food required", "Enter what you ate.", parent=self.event_window)
                    return
                carbs_text = amount_var.get().strip()
                carbs = None
                if carbs_text:
                    try:
                        carbs = float(carbs_text)
                    except ValueError:
                        carbs = None
                    if carbs is None or carbs < 0:
                        messagebox.showerror("Invalid carbohydrates", "Enter a positive carbohydrate amount or leave it blank.", parent=self.event_window)
                        return
                saved_event.update({"description": description, "serving": serving_var.get().strip(), "carbs_g": carbs})
            else:
                insulin_type = first_var.get().strip() or "Other"
                try:
                    units = float(amount_var.get().strip())
                except ValueError:
                    units = 0
                if units <= 0:
                    messagebox.showerror("Invalid amount", "Enter the amount injected in units.", parent=self.event_window)
                    return
                saved_event.update({"insulin_type": insulin_type, "insulin_units": units})
            if editing:
                self.events = [saved_event if item["id"] == saved_event["id"] else item for item in self.events]
            else:
                self.events.append(saved_event)
            self.events.sort(key=lambda item: item["time"])
            save_events(self.events)
            self.event_window.destroy()
            self.event_window = None
            label = "Food" if is_food else "Insulin"
            action = "updated" if editing else "recorded"
            self.status.set(f"{label} event {action} at {timestamp:%H:%M}.")
            self.update_display()
            if on_saved:
                on_saved()

        if is_food:
            tk.Button(buttons, text="Add food to list", command=add_food_to_database, bg="#7c3aed", fg="white", relief="flat", padx=10, pady=8).pack(side="left", padx=(0, 7))
        tk.Button(buttons, text="Save changes" if editing else "Save event", command=save_event, bg="#16a34a", fg="white", relief="flat", padx=16, pady=8).pack(side="left")
        tk.Button(buttons, text="Cancel", command=self.event_window.destroy, bg="#475569", fg="white", relief="flat", padx=16, pady=8).pack(side="right")

    def open_event_log(self):
        window = tk.Toplevel(self.root)
        window.title("Recorded timeline events")
        window.geometry("650x360")
        window.configure(bg="#111827")
        window.transient(self.root)
        tk.Label(window, text="Recorded timeline events", fg="#f8fafc", bg="#111827", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(window, text="Select an entry and edit it, or delete it if it was recorded incorrectly.", fg="#94a3b8", bg="#111827").pack(anchor="w", padx=20, pady=(0, 12))
        frame = tk.Frame(window, bg="#111827")
        frame.pack(fill="both", expand=True, padx=20)
        columns = ("time", "type", "details", "amount")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=9)
        for column, heading, width in [("time", "Time", 145), ("type", "Type", 85), ("details", "Details", 260), ("amount", "Amount", 100)]:
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        def refresh():
            tree.delete(*tree.get_children())
            for event in self.events:
                if event["type"] == "food":
                    details = event.get("description", "")
                    if event.get("serving"):
                        details += f" ({event['serving']})"
                    amount = f"{event['carbs_g']:g} g carbs" if isinstance(event.get("carbs_g"), (int, float)) else ""
                    label = "Food"
                else:
                    details = event.get("insulin_type", "Other")
                    amount = f"{event['insulin_units']:g} units"
                    label = "Insulin"
                tree.insert("", "end", iid=event["id"], values=(event["time"].strftime("%Y-%m-%d %H:%M"), label, details, amount))

        def delete_selected():
            selected = tree.selection()
            if not selected:
                return
            if not messagebox.askyesno("Delete event", "Delete the selected timeline event?", parent=window):
                return
            selected_ids = set(selected)
            self.events = [event for event in self.events if event["id"] not in selected_ids]
            save_events(self.events)
            refresh()
            self.update_display()

        def edit_selected():
            selected = tree.selection()
            if len(selected) != 1:
                return
            event_id = selected[0]
            selected_event = next((event for event in self.events if event["id"] == event_id), None)
            if not selected_event:
                return
            window.destroy()
            self.open_event_dialog(selected_event["type"], selected_event)

        refresh()
        buttons = tk.Frame(window, bg="#111827")
        buttons.pack(fill="x", padx=20, pady=14)
        tree.bind("<Double-1>", lambda event: edit_selected())
        tk.Button(buttons, text="Edit selected", command=edit_selected, bg="#2563eb", fg="white", relief="flat", padx=12, pady=7).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Delete selected", command=delete_selected, bg="#7f1d1d", fg="white", relief="flat", padx=12, pady=7).pack(side="left")
        tk.Button(buttons, text="Close", command=window.destroy, bg="#475569", fg="white", relief="flat", padx=12, pady=7).pack(side="right")

    def open_food_editor(self, index=None, initial=None, parent=None, on_saved=None):
        parent = parent or self.root
        window = tk.Toplevel(parent)
        window.title("Edit food" if index is not None else "Add food to database")
        window.geometry("470x300")
        window.resizable(False, False)
        window.configure(bg="#111827")
        window.transient(parent)
        food = dict(self.foods[index]) if index is not None else dict(initial or {})
        name_var = tk.StringVar(value=food.get("name", ""))
        serving_var = tk.StringVar(value=food.get("serving", ""))
        carbs_var = tk.StringVar(value=f"{food['carbs_g']:g}" if isinstance(food.get("carbs_g"), (int, float)) else "")
        auto_scale_base_serving = serving_var.get()
        auto_scale_base_carbs = food.get("carbs_g")
        tk.Label(window, text=window.title(), fg="#f8fafc", bg="#111827", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(window, text="These values are editable estimates used to prefill food entries.", fg="#94a3b8", bg="#111827", wraplength=410, justify="left").pack(anchor="w", padx=22, pady=(0, 14))
        form = tk.Frame(window, bg="#111827")
        form.pack(fill="x", padx=22)
        for row, label, variable in [(0, "Food name", name_var), (1, "Default serving", serving_var), (2, "Carbohydrates (g)", carbs_var)]:
            tk.Label(form, text=label, fg="#cbd5e1", bg="#111827").grid(row=row, column=0, sticky="w", pady=(0, 8))
            tk.Entry(form, textvariable=variable, width=38, relief="flat", font=("Segoe UI", 10)).grid(row=row, column=1, sticky="ew", pady=(0, 8), ipady=4)
        form.columnconfigure(1, weight=1)

        def update_database_carbs_from_serving(*_):
            scaled = scale_carbs_for_gram_serving(
                serving_var.get(), auto_scale_base_serving, auto_scale_base_carbs
            )
            if scaled is not None:
                carbs_var.set(f"{scaled:g}")

        serving_var.trace_add("write", update_database_carbs_from_serving)
        buttons = tk.Frame(window, bg="#111827")
        buttons.pack(fill="x", padx=22, pady=16)

        def save_food():
            name = name_var.get().strip()
            serving = serving_var.get().strip()
            try:
                carbs = float(carbs_var.get().strip())
            except ValueError:
                carbs = -1
            duplicate = next((food for pos, food in enumerate(self.foods) if pos != index and food["name"].casefold() == name.casefold()), None)
            if not name or not serving or carbs < 0:
                messagebox.showerror("Invalid food", "Enter a name, serving, and non-negative carbohydrate amount.", parent=window)
                return
            if duplicate:
                messagebox.showerror("Duplicate food", "A food with that name already exists.", parent=window)
                return
            updated = {"name": name, "serving": serving, "carbs_g": carbs}
            if index is None:
                self.foods.append(updated)
            else:
                self.foods[index] = updated
            self.foods.sort(key=lambda item: item["name"].casefold())
            save_foods(self.foods)
            window.destroy()
            if on_saved:
                on_saved()

        tk.Button(buttons, text="Save food", command=save_food, bg="#16a34a", fg="white", relief="flat", padx=16, pady=8).pack(side="left")
        tk.Button(buttons, text="Cancel", command=window.destroy, bg="#475569", fg="white", relief="flat", padx=16, pady=8).pack(side="right")

    def open_food_database(self):
        window = tk.Toplevel(self.root)
        window.title("Food database")
        window.geometry("800x650")
        window.configure(bg="#111827")
        window.transient(self.root)
        tk.Label(window, text="Food database", fg="#f8fafc", bg="#111827", font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(window, text="The UK source is the bundled CoFID 2021 database. You can edit the local list or optionally search USDA FoodData Central for USA foods.", fg="#94a3b8", bg="#111827", wraplength=740, justify="left").pack(anchor="w", padx=22, pady=(0, 12))

        region_bar = tk.Frame(window, bg="#111827")
        region_bar.pack(fill="x", padx=22, pady=(0, 10))
        tk.Label(region_bar, text="Food source", fg="#cbd5e1", bg="#111827").pack(side="left")
        region_var = tk.StringVar(value=FOOD_REGION_OPTIONS[0])
        region_box = ttk.Combobox(region_bar, textvariable=region_var, values=FOOD_REGION_OPTIONS, state="readonly", width=38)
        region_box.pack(side="left", padx=10)
        tk.Label(region_bar, text="UK uses bundled CoFID; USA enables official API search.", fg="#94a3b8", bg="#111827", font=("Segoe UI", 8)).pack(side="left")

        api_bar = tk.Frame(window, bg="#111827")
        api_bar.pack(fill="x", padx=22, pady=(0, 10))
        api_key_var = tk.StringVar(value=get_vault_password(FOODDATA_API_CREDENTIAL) or "")
        tk.Label(api_bar, text="FoodData Central API key (optional)", fg="#cbd5e1", bg="#111827").pack(side="left")
        api_entry = tk.Entry(api_bar, textvariable=api_key_var, show="•", width=32, relief="flat")
        api_entry.pack(side="left", padx=10, ipady=4)

        def save_api_key():
            key = api_key_var.get().strip()
            if key and set_vault_password(FOODDATA_API_CREDENTIAL, key):
                status_label.config(text="API key saved securely in Windows Credential Manager.")
            elif not key:
                delete_vault_password(FOODDATA_API_CREDENTIAL)
                status_label.config(text="API key removed.")
            else:
                status_label.config(text="Could not save the API key securely.")

        tk.Button(api_bar, text="Save key", command=save_api_key, bg="#334155", fg="white", relief="flat", padx=10, pady=5).pack(side="left")
        tk.Button(api_bar, text="Open API guide", command=lambda: webbrowser.open("https://fdc.nal.usda.gov/api-guide/"), bg="#334155", fg="white", relief="flat", padx=10, pady=5).pack(side="right")

        search_bar = tk.Frame(window, bg="#111827")
        search_bar.pack(fill="x", padx=22, pady=(0, 8))
        query_var = tk.StringVar()
        tk.Label(search_bar, text="Search official database", fg="#cbd5e1", bg="#111827").pack(side="left")
        tk.Entry(search_bar, textvariable=query_var, width=32, relief="flat").pack(side="left", padx=10, ipady=4)
        search_button = tk.Button(search_bar, text="Search", bg="#2563eb", fg="white", relief="flat", padx=12, pady=5)
        search_button.pack(side="left")
        status_label = tk.Label(window, text="UK CoFID foods work offline; the USA search needs your own API key.", fg="#94a3b8", bg="#111827", anchor="w")
        status_label.pack(fill="x", padx=22, pady=(0, 6))

        result_frame = tk.Frame(window, bg="#111827")
        result_frame.pack(fill="both", expand=True, padx=22)
        result_tree = ttk.Treeview(result_frame, columns=("name", "serving", "carbs"), show="headings", height=7)
        for column, heading, width in [("name", "Official food", 320), ("serving", "Serving", 180), ("carbs", "Carbs g", 100)]:
            result_tree.heading(column, text=heading)
            result_tree.column(column, width=width, anchor="w")
        result_tree.pack(fill="x", pady=(0, 10))
        result_list = []

        def show_results(items):
            result_list.clear()
            result_list.extend(items)
            result_tree.delete(*result_tree.get_children())
            for pos, food in enumerate(items):
                result_tree.insert("", "end", iid=str(pos), values=(food["name"], food["serving"], f"{food['carbs_g']:g}"))

        def search_official():
            query = query_var.get().strip()
            if not query:
                status_label.config(text="Enter a food name to search.")
                return
            if region_var.get().startswith("UK"):
                matches = [food for food in self.foods if query.casefold() in food["name"].casefold()]
                show_results(matches)
                status_label.config(text=f"Found {len(matches)} matching UK CoFID/local foods. Edit the local list if needed.")
                return
            key = api_key_var.get().strip()
            if not key:
                status_label.config(text="Add your own FoodData Central API key first; it is not included in this app.")
                return
            search_button.config(state="disabled", text="Searching…")
            status_label.config(text="Searching FoodData Central…")

            def worker():
                items = []
                error = None
                try:
                    response = requests.get(FOODDATA_SEARCH_URL, params={"api_key": key, "query": query, "pageSize": 20}, timeout=(5, 20))
                    response.raise_for_status()
                    for item in response.json().get("foods", []):
                        nutrients = item.get("foodNutrients", [])
                        carbohydrate = next((nutrient.get("value") for nutrient in nutrients if str(nutrient.get("nutrientNumber")) == "1005" or "carbohydrate" in str(nutrient.get("nutrientName", "")).lower()), None)
                        if carbohydrate is None:
                            continue
                        try:
                            carbs_per_100g = float(carbohydrate)
                        except (TypeError, ValueError):
                            continue
                        serving_size = item.get("servingSize")
                        serving_unit = item.get("servingSizeUnit") or "g"
                        try:
                            serving_size_value = float(serving_size)
                        except (TypeError, ValueError):
                            serving_size_value = None
                        if serving_size_value and str(serving_unit).lower() == "g":
                            serving = f"{serving_size_value:g} g"
                            carbs = carbs_per_100g * serving_size_value / 100
                        else:
                            serving = "100 g"
                            carbs = carbs_per_100g
                        items.append({"name": str(item.get("description") or query), "serving": serving, "carbs_g": round(carbs, 1)})
                except Exception:
                    error = "Official food search failed. Check the API key and internet connection."
                self.root.after(0, lambda: finish_search(items, error))

            threading.Thread(target=worker, daemon=True).start()

        def finish_search(items, error):
            search_button.config(state="normal", text="Search")
            if error:
                status_label.config(text=error)
                return
            show_results(items)
            status_label.config(text=f"Found {len(items)} official results. Select one to copy it to the local list.")

        search_button.config(command=search_official)

        def source_changed(event=None):
            if region_var.get().startswith("UK"):
                status_label.config(text="UK source selected: searching the bundled CoFID 2021 database and your local edits.")
            else:
                status_label.config(text="USA source selected: enter your own FoodData Central API key for official search.")

        region_box.bind("<<ComboboxSelected>>", source_changed)

        local_label = tk.Label(window, text="Local editable foods", fg="#f8fafc", bg="#111827", font=("Segoe UI", 11, "bold"))
        local_label.pack(anchor="w", padx=22, pady=(0, 5))
        local_tree = ttk.Treeview(window, columns=("name", "serving", "carbs"), show="headings", height=8)
        for column, heading, width in [("name", "Food", 320), ("serving", "Default serving", 220), ("carbs", "Carbs g", 100)]:
            local_tree.heading(column, text=heading)
            local_tree.column(column, width=width, anchor="w")
        local_tree.pack(fill="both", expand=True, padx=22)

        def refresh_local():
            local_tree.delete(*local_tree.get_children())
            for pos, food in enumerate(self.foods):
                local_tree.insert("", "end", iid=str(pos), values=(food["name"], food["serving"], f"{food['carbs_g']:g}"))

        def add_selected_result():
            selected = result_tree.selection()
            if not selected:
                return
            food = result_list[int(selected[0])]
            self.open_food_editor(initial=food, parent=window, on_saved=refresh_local)

        def edit_local():
            selected = local_tree.selection()
            if selected:
                self.open_food_editor(index=int(selected[0]), parent=window, on_saved=refresh_local)

        def delete_local():
            selected = local_tree.selection()
            if not selected:
                return
            if not messagebox.askyesno("Delete food", "Delete the selected food from the local database?", parent=window):
                return
            self.foods.pop(int(selected[0]))
            save_foods(self.foods)
            refresh_local()

        buttons = tk.Frame(window, bg="#111827")
        buttons.pack(fill="x", padx=22, pady=12)
        tk.Button(buttons, text="Copy selected result", command=add_selected_result, bg="#2563eb", fg="white", relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(buttons, text="Add local", command=lambda: self.open_food_editor(parent=window, on_saved=refresh_local), bg="#16a34a", fg="white", relief="flat", padx=10, pady=6).pack(side="left", padx=6)
        tk.Button(buttons, text="Edit local", command=edit_local, bg="#475569", fg="white", relief="flat", padx=10, pady=6).pack(side="left", padx=6)
        tk.Button(buttons, text="Delete local", command=delete_local, bg="#7f1d1d", fg="white", relief="flat", padx=10, pady=6).pack(side="left", padx=6)
        tk.Button(buttons, text="Close", command=window.destroy, bg="#475569", fg="white", relief="flat", padx=10, pady=6).pack(side="right")
        refresh_local()

    def export_recordings(self):
        path = filedialog.asksaveasfilename(
            title="Export glucose and timeline data",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")],
            initialfile="libre-glucose-timeline.csv",
        )
        if not path:
            return
        try:
            export_recording_data(path, self.readings, self.events)
            self.status.set("Readings and timeline events exported. No dose recommendation was added.")
        except OSError as error:
            messagebox.showerror("Export failed", f"The recording data could not be exported.\n{error}", parent=self.root)

    def get_virtual_screen_bounds(self):
        try:
            if os.name == "nt":
                user32 = ctypes.windll.user32
                left = user32.GetSystemMetrics(76)
                top = user32.GetSystemMetrics(77)
                width = user32.GetSystemMetrics(78)
                height = user32.GetSystemMetrics(79)
                if width and height:
                    return left, top, left + width, top + height
        except (AttributeError, OSError):
            pass
        try:
            left = int(self.root.winfo_vrootx())
            top = int(self.root.winfo_vrooty())
            return left, top, left + int(self.root.winfo_vrootwidth()), top + int(self.root.winfo_vrootheight())
        except tk.TclError:
            return 0, 0, int(self.root.winfo_screenwidth()), int(self.root.winfo_screenheight())

    def keep_overlay_on_screen(self):
        size = OVERLAY_SIZES.get(self.overlay_size.get(), OVERLAY_SIZES["Medium"])
        self.overlay_x, self.overlay_y = clamp_overlay_position(
            self.overlay_x,
            self.overlay_y,
            size["width"],
            size["height"],
            self.get_virtual_screen_bounds(),
        )

    def reset_overlay_position(self):
        self.overlay_x, self.overlay_y = clamp_overlay_position(
            30,
            30,
            OVERLAY_SIZES["Medium"]["width"],
            OVERLAY_SIZES["Medium"]["height"],
            self.get_virtual_screen_bounds(),
        )
        self.save_overlay_position()
        if self.overlay and self.overlay.winfo_exists():
            self.apply_overlay_style()
        self.status.set("Overlay position reset.")

    def export_visual_settings(self):
        self.save_overlay_position()
        path = filedialog.asksaveasfilename(
            title="Export overlay appearance",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="libre-overlay-appearance.json",
        )
        if not path:
            return
        data = {"format": "Libre Desktop Overlay appearance", "version": 1}
        data.update({
            "unit": self.unit.get(),
            "always_on_top": self.always_on_top.get(),
            "overlay_color": self.overlay_color.get(),
            "overlay_background_opacity": self.overlay_background_opacity.get(),
            "overlay_number_opacity": self.overlay_number_opacity.get(),
            "overlay_size": self.overlay_size.get(),
            "overlay_locked": self.overlay_locked.get(),
            "overlay_x": self.overlay_x,
            "overlay_y": self.overlay_y,
        })
        try:
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.status.set("Appearance exported without connection credentials.")
        except OSError as error:
            messagebox.showerror("Export failed", f"The appearance settings could not be saved.\n{error}", parent=self.root)

    def import_visual_settings(self):
        path = filedialog.askopenfilename(
            title="Import overlay appearance",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("The file does not contain appearance settings.")
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror("Import failed", f"The appearance settings could not be read.\n{error}", parent=self.root)
            return

        if data.get("overlay_color") in OVERLAY_COLORS:
            self.overlay_color.set(data["overlay_color"])
        if data.get("overlay_size") in OVERLAY_SIZES:
            self.overlay_size.set(data["overlay_size"])
        if data.get("unit") in ("mmol/L", "mg/dL"):
            self.unit.set(data["unit"])
        if isinstance(data.get("always_on_top"), bool):
            self.always_on_top.set(data["always_on_top"])
        for key, variable, fallback in [
            ("overlay_background_opacity", self.overlay_background_opacity, 82),
            ("overlay_number_opacity", self.overlay_number_opacity, 100),
        ]:
            if key in data:
                try:
                    variable.set(max(35, min(100, int(data[key]))))
                except (TypeError, ValueError):
                    variable.set(fallback)
        if isinstance(data.get("overlay_locked"), bool):
            self.overlay_locked.set(data["overlay_locked"])
        for key in ("overlay_x", "overlay_y"):
            if key in data:
                try:
                    setattr(self, key, int(data[key]))
                except (TypeError, ValueError):
                    pass
        self.keep_overlay_on_screen()
        self.settings.update({
            "unit": self.unit.get(),
            "always_on_top": self.always_on_top.get(),
            "overlay_color": self.overlay_color.get(),
            "overlay_background_opacity": self.overlay_background_opacity.get(),
            "overlay_number_opacity": self.overlay_number_opacity.get(),
            "overlay_size": self.overlay_size.get(),
            "overlay_locked": self.overlay_locked.get(),
            "overlay_x": self.overlay_x,
            "overlay_y": self.overlay_y,
        })
        save_settings(self.settings)
        self.update_overlay_topmost()
        if self.overlay and self.overlay.winfo_exists():
            self.apply_overlay_style()
        self.status.set("Appearance imported. Connection details were not changed.")

    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("About Libre Desktop Overlay")
        about.geometry("520x410")
        about.resizable(False, False)
        about.configure(bg="#111827")
        about.transient(self.root)
        tk.Label(about, text="Libre Desktop Overlay", fg="#f8fafc", bg="#111827", font=("Segoe UI", 17, "bold")).pack(pady=(24, 4))
        tk.Label(about, text=f"Version {APP_VERSION}", fg="#38bdf8", bg="#111827", font=("Segoe UI", 10)).pack()
        tk.Label(
            about,
            text=(
                "Libre Desktop Overlay is an unofficial, independently developed Windows companion display.\n\n"
                "It can read locally from Juggluco on an Android phone, or from a user-authorised Gluroo Global Connect feed.\n\n"
                "It is not affiliated with, endorsed by or supported by Juggluco, Gluroo, Abbott or the Nightscout project."
            ),
            fg="#cbd5e1",
            bg="#111827",
            justify="left",
            anchor="w",
            wraplength=450,
        ).pack(fill="x", padx=30, pady=14)
        tk.Button(about, text="Open GitHub releases", command=lambda: webbrowser.open(GITHUB_RELEASES_URL), bg="#334155", fg="white", relief="flat", padx=12, pady=7).pack()
        tk.Label(about, text="This application is a secondary convenience display only. Verify readings using the official CGM application before making insulin or treatment decisions.", fg="#fbbf24", bg="#111827", wraplength=450, justify="left", font=("Segoe UI", 9, "bold")).pack(fill="x", padx=30, pady=10)
        tk.Button(about, text="Close", command=about.destroy, bg="#475569", fg="white", relief="flat", padx=14, pady=6).pack()

    @staticmethod
    def version_tuple(version):
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", str(version))
        return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)

    @staticmethod
    def is_allowed_update_url(asset_url):
        parsed = urlparse(str(asset_url))
        expected_path = f"/{GITHUB_REPOSITORY}/releases/download/"
        return parsed.scheme == "https" and parsed.netloc == "github.com" and parsed.path.startswith(expected_path)

    @staticmethod
    def update_directory():
        """Return a directory that this installation can use for update files."""
        candidates = [Path(tempfile.gettempdir())]
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "LibreViewDesktopOverlay" / "updates")
        candidates.append(APP_DATA_DIR / "updates")
        for candidate in candidates:
            probe = candidate / ".write-test"
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                probe.write_bytes(b"")
                probe.unlink(missing_ok=True)
                return candidate
            except OSError:
                try:
                    probe.unlink(missing_ok=True)
                except OSError:
                    pass
        raise OSError("No writable folder is available for the update.")

    @staticmethod
    def github_request(url, **kwargs):
        """Request GitHub normally, then retry directly if a proxy is unavailable."""
        try:
            return requests.get(url, **kwargs)
        except requests.exceptions.ProxyError:
            session = requests.Session()
            session.trust_env = False
            return session.get(url, **kwargs)

    def auto_check_for_updates(self):
        if self.auto_check_updates.get() and not self.exiting:
            self.check_for_updates(silent=True)

    def check_for_updates(self, silent=False):
        if self.update_busy:
            return
        self.update_busy = True
        self.update_button.config(state="disabled", text="Checking…")
        if not silent:
            self.status.set("Checking GitHub for an application update…")

        def worker():
            try:
                response = self.github_request(
                    GITHUB_RELEASES_API,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": f"LibreDesktopOverlay/{APP_VERSION}",
                    },
                    timeout=(5, 20),
                )
                response.raise_for_status()
                release = response.json()
                self.worker_results.put(("update_checked", dt.datetime.now()))
                latest_tag = str(release.get("tag_name", ""))
                latest_version = latest_tag.lstrip("vV")
                if self.version_tuple(latest_version) <= self.version_tuple(APP_VERSION):
                    self.worker_results.put(("update_up_to_date", silent))
                    return
                asset = next(
                    (item for item in release.get("assets", []) if item.get("name") == UPDATE_ASSET_NAME),
                    None,
                )
                asset_url = asset.get("browser_download_url") if asset else None
                if not latest_version or not asset_url or not self.is_allowed_update_url(asset_url):
                    self.worker_results.put(("update_error", "A valid installer was not found in the latest release.", silent))
                    return
                self.worker_results.put(("update_available", latest_version, asset_url, silent))
            except Exception:
                self.worker_results.put(("update_error", "Could not check GitHub for an update.", silent))

        threading.Thread(target=worker, daemon=True).start()

    def start_juggluco_connection(self, session, api_secret, remember, login_window):
        self.provider_generation += 1
        generation = self.provider_generation
        self.live_provider_name = "Juggluco"
        self.cloud_busy = True
        self.last_cloud_attempt = dt.datetime.now()
        self.last_connection_error = None
        self.live_button.config(state="disabled", text="Connecting…")
        self.status.set("Connecting to Juggluco over the local network…")
        self.update_diagnostics()
        def worker():
            try:
                readings = session.fetch()
                saved_ok = set_vault_password("juggluco-api-secret", api_secret) if remember and api_secret else True
                if not remember:
                    delete_vault_password("juggluco-api-secret")
                self.worker_results.put(("connected", generation, session, readings, "Juggluco", remember, saved_ok, login_window))
            except (CloudLoginError, CloudSetupError) as error:
                self.worker_results.put(("connect_error", generation, str(error), login_window))
            except Exception:
                self.worker_results.put(("connect_error", generation, "Unexpected Juggluco connection error.", login_window))
        threading.Thread(target=worker, daemon=True).start()

    def launch_installer_and_restart(self, installer_path):
        """Run the installer after this process exits; the installer launches the app."""
        installer = Path(installer_path).resolve()
        if not installer.exists():
            return False
        script = Path(tempfile.gettempdir()) / f"LibreDesktopOverlay-update-{os.getpid()}.cmd"
        process_id = os.getpid()
        script_text = "\r\n".join([
            "@echo off",
            "setlocal",
            ":wait_for_app",
            f'tasklist /FI "PID eq {process_id}" /NH | findstr /C:" {process_id} " >nul',
            "if not errorlevel 1 (",
            "  timeout /t 1 /nobreak >nul",
            "  goto wait_for_app",
            ")",
            f'start "" /wait "{installer}"',
            'del "%~f0"',
            "",
        ])
        script.write_text(script_text, encoding="utf-8")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["cmd.exe", "/d", "/c", str(script)],
            cwd=str(installer.parent),
            close_fds=True,
            creationflags=creation_flags,
        )
        return True

    def download_update(self, asset_url, version):
        if self.update_busy:
            return
        self.update_busy = True
        self.update_button.config(state="disabled", text="Downloading…")
        self.status.set(f"Downloading Libre Desktop Overlay {version}…")

        def worker():
            temporary_path = None
            try:
                if not self.is_allowed_update_url(asset_url):
                    raise ValueError("The update download URL was not trusted.")
                destination = self.update_directory() / f"LibreDesktopOverlay-Setup-{version}.exe"
                temporary_path = destination.with_suffix(destination.suffix + ".part")
                temporary_path.unlink(missing_ok=True)
                response = self.github_request(
                    asset_url,
                    headers={
                        "Accept": "application/octet-stream",
                        "User-Agent": f"LibreDesktopOverlay/{APP_VERSION}",
                    },
                    stream=True,
                    timeout=(5, 60),
                )
                response.raise_for_status()
                total = 0
                with temporary_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > UPDATE_MAX_BYTES:
                            raise ValueError("The update file is unexpectedly large.")
                        handle.write(chunk)
                temporary_path.replace(destination)
                self.worker_results.put(("update_downloaded", str(destination)))
            except requests.exceptions.RequestException:
                if temporary_path:
                    temporary_path.unlink(missing_ok=True)
                self.worker_results.put((
                    "update_download_error",
                    "GitHub did not return the installer. Check your internet connection and try again.",
                ))
            except OSError:
                if temporary_path:
                    temporary_path.unlink(missing_ok=True)
                self.worker_results.put((
                    "update_download_error",
                    "The installer could not be saved. Check disk space and try again.",
                ))
            except Exception:
                if temporary_path:
                    temporary_path.unlink(missing_ok=True)
                self.worker_results.put(("update_download_error", "The update could not be downloaded."))

        threading.Thread(target=worker, daemon=True).start()

    def load_file(self, path):
        try:
            csv_readings = load_libreview_csv(path)
            self.provider_generation += 1
            self.cloud_busy = False
            self.readings = csv_readings
            self.csv_path = path
            self.last_modified = os.path.getmtime(path)
            self.data_source = "csv"
            self.last_successful_refresh = dt.datetime.now()
            self.last_connection_error = None
            self.status.set(f"CSV fallback • loaded {len(self.readings):,} readings • watching for changes")
            self.update_diagnostics()
            self.update_display()
            if self.overlay_enabled.get():
                self.show_overlay()
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not load LibreView data", str(error))

    def poll_file(self):
        self.file_refresh_job = None
        if self.csv_path and self.data_source == "csv":
            try:
                modified = os.path.getmtime(self.csv_path)
                if self.last_modified != modified:
                    self.load_file(self.csv_path)
            except OSError:
                pass
        self.file_refresh_job = self.root.after(int(self.refresh_interval.get()) * 1000, self.poll_file)

    def on_unit_change(self, *args):
        self.settings["unit"] = self.unit.get()
        save_settings(self.settings)
        if hasattr(self, "current_unit"):
            self.current_unit.config(text=self.unit.get())
            self.update_display()

    def enable_overlay(self):
        self.overlay_enabled.set(True)
        self.settings["overlay_enabled"] = True
        save_settings(self.settings)
        self.show_overlay()

    def disable_overlay(self):
        self.save_overlay_position()
        self.overlay_enabled.set(False)
        self.settings["overlay_enabled"] = False
        save_settings(self.settings)
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.withdraw()
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.withdraw()

    def toggle_overlay(self):
        if self.overlay_enabled.get():
            self.enable_overlay()
        else:
            self.disable_overlay()

    def on_overlay_style_change(self, *args):
        self.settings["overlay_color"] = self.overlay_color.get()
        self.settings["overlay_background_opacity"] = int(self.overlay_background_opacity.get())
        self.settings["overlay_number_opacity"] = int(self.overlay_number_opacity.get())
        save_settings(self.settings)
        self.apply_overlay_style()

    def on_overlay_size_change(self, *args):
        if self.overlay_size.get() not in OVERLAY_SIZES:
            self.overlay_size.set("Medium")
            return
        self.settings["overlay_size"] = self.overlay_size.get()
        save_settings(self.settings)
        self.apply_overlay_style()

    def toggle_overlay_lock(self):
        self.settings["overlay_locked"] = self.overlay_locked.get()
        save_settings(self.settings)

    def toggle_always_on_top(self):
        self.settings["always_on_top"] = self.always_on_top.get()
        save_settings(self.settings)
        self.update_overlay_topmost()

    def toggle_start_overlay(self):
        self.settings["start_overlay"] = self.start_overlay.get()
        save_settings(self.settings)

    def toggle_start_hidden(self):
        self.settings["start_hidden"] = self.start_hidden.get()
        save_settings(self.settings)

    def toggle_start_with_windows(self):
        enabled = self.start_with_windows.get()
        if not set_windows_startup(enabled):
            self.start_with_windows.set(not enabled)
            messagebox.showerror(
                "Startup setting unavailable",
                "Windows startup registration could not be changed.",
                parent=self.root,
            )
            return
        self.settings["start_with_windows"] = enabled
        save_settings(self.settings)

    def apply_overlay_style(self):
        if not self.overlay or not self.overlay.winfo_exists():
            return
        self.keep_overlay_on_screen()
        bg = OVERLAY_COLORS.get(self.overlay_color.get(), OVERLAY_COLORS["Navy"])
        background_opacity = max(35, min(100, int(self.overlay_background_opacity.get()))) / 100
        number_opacity = max(35, min(100, int(self.overlay_number_opacity.get()))) / 100
        size = OVERLAY_SIZES.get(self.overlay_size.get(), OVERLAY_SIZES["Medium"])
        geometry = f"{size['width']}x{size['height']}+{self.overlay_x}+{self.overlay_y}"
        self.overlay.geometry(geometry)
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.geometry(geometry)
        self.overlay.configure(bg=bg)
        self.overlay.attributes("-alpha", background_opacity)
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.attributes("-alpha", number_opacity)
        widgets = [self.overlay_value_row, self.overlay_close_button, self.overlay_minimize_button, *self.overlay_labels.values()]
        for widget in widgets:
            if widget and widget.winfo_exists():
                try:
                    widget.configure(bg=OVERLAY_TRANSPARENT_COLOR if self.overlay_text_transparent else bg)
                except tk.TclError:
                    pass
        if self.overlay_labels:
            self.overlay_labels["value"].configure(font=size["value_font"])
            self.overlay_labels["trend"].configure(font=size["trend_font"])
            self.overlay_labels["unit"].configure(font=size["unit_font"])
            self.overlay_labels["time"].configure(font=size["time_font"])
        self.raise_overlay_layers()

    def raise_overlay_layers(self):
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.lift()
        if self.overlay_text and self.overlay_text.winfo_exists():
            if self.overlay and self.overlay.winfo_exists():
                self.overlay_text.lift(self.overlay)
            else:
                self.overlay_text.lift()

    @staticmethod
    def set_overlay_click_through(window, enabled):
        """Make a Windows overlay return transparent hit tests when requested."""
        if window is None or os.name != "nt" or not window.winfo_exists():
            return
        try:
            user32 = ctypes.windll.user32
            hwnd = window.winfo_id()
            get_proc = user32.GetWindowLongPtrW
            set_proc = user32.SetWindowLongPtrW
            call_proc = user32.CallWindowProcW
            get_proc.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_proc.restype = ctypes.c_ssize_t
            set_proc.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            set_proc.restype = ctypes.c_ssize_t
            call_proc.argtypes = [
                ctypes.c_ssize_t,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            call_proc.restype = ctypes.c_ssize_t
            get_style = user32.GetWindowLongPtrW
            set_style = user32.SetWindowLongPtrW
            get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_style.restype = ctypes.c_ssize_t
            set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            set_style.restype = ctypes.c_ssize_t
            style = get_style(hwnd, WINDOWS_GWL_EXSTYLE)
            if enabled:
                style |= WINDOWS_WS_EX_LAYERED | WINDOWS_WS_EX_TRANSPARENT
            else:
                style &= ~WINDOWS_WS_EX_TRANSPARENT
            set_style(hwnd, WINDOWS_GWL_EXSTYLE, style)
            if enabled:
                # Tk already configured the alpha/color-key state; reapplying
                # alpha after changing the native style makes Windows repaint
                # the existing layered surface instead of showing it black.
                window.attributes("-alpha", window.attributes("-alpha"))
                window.update_idletasks()
            if enabled and hwnd not in getattr(window, "_click_through_procs", {}):
                callback_type = ctypes.WINFUNCTYPE(
                    ctypes.c_ssize_t,
                    ctypes.c_void_p,
                    ctypes.c_uint,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                )
                old_proc = get_proc(hwnd, WINDOWS_GWLP_WNDPROC)

                def window_proc(message_hwnd, message, wparam, lparam):
                    if message == WINDOWS_WM_NCHITTEST:
                        return WINDOWS_HTTRANSPARENT
                    if message == WINDOWS_WM_MOUSEACTIVATE:
                        return WINDOWS_MA_NOACTIVATE
                    return call_proc(old_proc, message_hwnd, message, wparam, lparam)

                callback = callback_type(window_proc)
                set_proc(hwnd, WINDOWS_GWLP_WNDPROC, ctypes.cast(callback, ctypes.c_void_p).value)
                window._click_through_procs = getattr(window, "_click_through_procs", {})
                window._click_through_procs[hwnd] = (old_proc, callback)
            elif not enabled and hwnd in getattr(window, "_click_through_procs", {}):
                old_proc, _callback = window._click_through_procs.pop(hwnd)
                set_proc(hwnd, WINDOWS_GWLP_WNDPROC, old_proc)
        except (AttributeError, OSError, tk.TclError):
            # Click-through is a convenience; it must not prevent the overlay
            # from working on older Windows/Tk combinations.
            pass

    def minimize_main(self):
        self.save_overlay_position()
        self.root.withdraw()
        if self.overlay_enabled.get():
            self.show_overlay()

    def handle_root_unmap(self, event=None):
        if not self.exiting and self.root.state() == "iconic":
            self.root.after_idle(self.minimize_main)

    def show_main(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def create_tray_image(self):
        image = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(30, 41, 59, 255), outline=(56, 189, 248, 255), width=3)
        draw.ellipse((17, 17, 47, 47), fill=(22, 163, 74, 255))
        draw.rectangle((29, 23, 35, 41), fill=(248, 250, 252, 255))
        return image

    def start_tray_icon(self):
        if pystray is None or self.tray_icon is not None:
            return

        def run_on_main(callback):
            if not self.exiting:
                self.root.after(0, callback)

        menu = pystray.Menu(
            pystray.MenuItem("Show main window", lambda icon, item: run_on_main(self.show_main), default=True),
            pystray.MenuItem("Show overlay", lambda icon, item: run_on_main(self.enable_overlay)),
            pystray.MenuItem("Exit", lambda icon, item: run_on_main(self.exit_application)),
        )
        self.tray_icon = pystray.Icon(
            "libre_desktop_overlay",
            self.create_tray_image(),
            "Libre Desktop Overlay",
            menu,
        )
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()

    def minimize_overlay(self):
        self.save_overlay_position()
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.withdraw()
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.withdraw()

    def exit_application(self):
        self.save_overlay_position()
        self.exiting = True
        if self.tray_icon:
            self.tray_icon.stop()
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.destroy()
        self.root.destroy()

    def refresh_freshness(self):
        if self.readings:
            self.update_display()
        self.root.after(30_000, self.refresh_freshness)

    def update_display(self):
        if not self.readings:
            return
        latest = self.readings[-1]
        age_minutes = max(0, (dt.datetime.now() - latest["time"]).total_seconds() / 60)
        warning = age_minutes >= WARNING_AFTER_MINUTES
        stale = age_minutes >= STALE_AFTER_MINUTES
        value_color = "#ef4444" if stale else "#f59e0b" if warning else self.glucose_color(latest["mgdl"])
        self.current_value.config(text=format_glucose(latest["mgdl"], self.unit.get()), fg=value_color)
        self.current_trend.config(text=latest.get("trend", ""))
        age_text = "just now" if age_minutes < 1 else f"{age_minutes:.0f} min ago"
        freshness_text = "\nSTALE DATA" if stale else "\nUPDATES DELAYED" if warning else ""
        freshness_color = "#ef4444" if stale else "#f59e0b" if warning else "#cbd5e1"
        self.current_time.config(text=f"Reading: {latest['time']:%d %b %Y %H:%M}\n{age_text}{freshness_text}", fg=freshness_color)
        self.draw_graph()
        self.update_overlay()

    @staticmethod
    def glucose_color(mgdl):
        if mgdl < 70:
            return "#ef4444"
        if mgdl > 180:
            return "#f59e0b"
        return "#22c55e"

    def hide_graph_event_tooltip(self, event=None):
        if self.graph_tooltip and self.graph_tooltip.winfo_exists():
            self.graph_tooltip.destroy()
        self.graph_tooltip = None

    def show_graph_event_tooltip(self, canvas_event, event_record):
        self.hide_graph_event_tooltip()
        color = EVENT_COLORS.get(event_record.get("type"), "#334155")
        tooltip = tk.Toplevel(self.root)
        tooltip.overrideredirect(True)
        tooltip.configure(bg=color)
        tooltip.attributes("-topmost", True)
        tk.Label(
            tooltip,
            text=format_event_tooltip(event_record),
            fg="#ffffff",
            bg=color,
            justify="left",
            anchor="w",
            padx=9,
            pady=7,
            font=("Segoe UI", 9),
        ).pack()
        tooltip.update_idletasks()
        x = canvas_event.x_root + 12
        y = canvas_event.y_root + 12
        width = tooltip.winfo_width()
        height = tooltip.winfo_height()
        if x + width > self.root.winfo_screenwidth():
            x = max(0, canvas_event.x_root - width - 12)
        if y + height > self.root.winfo_screenheight():
            y = max(0, canvas_event.y_root - height - 12)
        tooltip.geometry(f"+{x}+{y}")
        self.graph_tooltip = tooltip

    def draw_graph(self):
        self.hide_graph_event_tooltip()
        self.canvas.delete("all")
        if not self.readings:
            self.canvas.create_text(300, 100, text="Connect Juggluco or Gluroo, or load a CSV to see the graph", fill="#94a3b8", font=("Segoe UI", 12))
            return
        width = max(self.canvas.winfo_width(), 400)
        height = max(self.canvas.winfo_height(), 220)
        end_time = self.readings[-1]["time"]
        start_time = end_time - dt.timedelta(hours=12)
        data = [item for item in self.readings if item["time"] >= start_time]
        unit = self.unit.get()
        values = [display_value(item["mgdl"], unit) for item in data]
        low_line = 3.9 if unit == "mmol/L" else 70
        high_line = 10.0 if unit == "mmol/L" else 180
        padding = 0.6 if unit == "mmol/L" else 10
        lo, hi = min(min(values), low_line) - padding, max(max(values), high_line) + padding
        left, top, right, bottom = 55, 18, width - 18, height - 30
        for level in [low_line, high_line]:
            y = bottom - ((level - lo) / (hi - lo)) * (bottom - top)
            self.canvas.create_line(left, y, right, y, fill="#334155", dash=(3, 4))
            label = f"{level:.1f}" if unit == "mmol/L" else f"{level:.0f}"
            self.canvas.create_text(left - 8, y, text=label, fill="#f59e0b", anchor="e", font=("Segoe UI", 9))
        time_span = max((end_time - start_time).total_seconds(), 1)
        segments = []
        segment = []
        previous_time = None
        for item, value in zip(data, values):
            if previous_time and item["time"] - previous_time > dt.timedelta(minutes=15):
                if segment:
                    segments.append(segment)
                segment = []
            x = left + ((item["time"] - start_time).total_seconds() / time_span) * (right - left)
            y = bottom - ((value - lo) / (hi - lo)) * (bottom - top)
            segment.extend([x, y])
            previous_time = item["time"]
        if segment:
            segments.append(segment)
        for points in segments:
            if len(points) >= 4:
                self.canvas.create_line(*points, fill="#38bdf8", width=3)
        for event in self.events:
            if start_time <= event["time"] <= end_time:
                nearest = min(data, key=lambda item: abs(item["time"] - event["time"]))
                event_value = display_value(nearest["mgdl"], unit)
                x = left + ((event["time"] - start_time).total_seconds() / time_span) * (right - left)
                y = bottom - ((event_value - lo) / (hi - lo)) * (bottom - top)
                color = EVENT_COLORS.get(event["type"], "#cbd5e1")
                marker = self.canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill=color, outline="#f8fafc", width=1)
                self.canvas.tag_bind(marker, "<Enter>", lambda canvas_event, record=event: self.show_graph_event_tooltip(canvas_event, record))
                self.canvas.tag_bind(marker, "<Leave>", self.hide_graph_event_tooltip)
                label = "Food" if event["type"] == "food" else "Insulin"
                self.canvas.create_text(x + 10, y, text=label, fill=color, anchor="w", font=("Segoe UI", 8, "bold"))
        last_points = segments[-1]
        self.canvas.create_oval(last_points[-2] - 5, last_points[-1] - 5, last_points[-2] + 5, last_points[-1] + 5, fill="#f8fafc", outline="#38bdf8", width=2)
        self.canvas.create_text(left, height - 10, text=start_time.strftime("%d %b %H:%M"), fill="#64748b", anchor="w", font=("Segoe UI", 9))
        self.canvas.create_text(right, height - 10, text=end_time.strftime("%d %b %H:%M"), fill="#64748b", anchor="e", font=("Segoe UI", 9))

    def show_overlay(self):
        if not self.overlay_enabled.get():
            return
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.deiconify()
            if self.overlay_text and self.overlay_text.winfo_exists():
                self.overlay_text.deiconify()
            self.apply_overlay_style()
            return
        bg = OVERLAY_COLORS.get(self.overlay_color.get(), OVERLAY_COLORS["Navy"])
        size = OVERLAY_SIZES.get(self.overlay_size.get(), OVERLAY_SIZES["Medium"])
        self.keep_overlay_on_screen()
        self.overlay = tk.Toplevel(self.root)
        self.overlay.title("Libre")
        self.overlay.geometry(f"{size['width']}x{size['height']}+{self.overlay_x}+{self.overlay_y}")
        self.overlay.configure(bg=bg)
        self.overlay.attributes("-topmost", self.always_on_top.get())
        self.overlay.resizable(False, False)
        self.overlay.overrideredirect(True)
        self.overlay.protocol("WM_DELETE_WINDOW", self.exit_application)
        self.overlay.bind("<FocusIn>", lambda event: self.raise_overlay_layers())
        self.overlay_text = tk.Toplevel(self.root)
        self.overlay_text.title("Libre reading")
        self.overlay_text.geometry(f"{size['width']}x{size['height']}+{self.overlay_x}+{self.overlay_y}")
        self.overlay_text.configure(bg=OVERLAY_TRANSPARENT_COLOR)
        self.overlay_text.attributes("-topmost", self.always_on_top.get())
        self.overlay_text.resizable(False, False)
        self.overlay_text.overrideredirect(True)
        try:
            self.overlay_text.attributes("-transparentcolor", OVERLAY_TRANSPARENT_COLOR)
            self.overlay_text_transparent = True
        except tk.TclError:
            self.overlay_text_transparent = False
        self.overlay_text.bind("<Escape>", lambda event: self.exit_application())
        self.overlay_text.bind("<FocusIn>", lambda event: self.raise_overlay_layers())
        top_row = tk.Frame(self.overlay_text, bg=OVERLAY_TRANSPARENT_COLOR if self.overlay_text_transparent else bg, height=34)
        top_row.pack(fill="x", padx=6, pady=(2, 0))
        top_row.pack_propagate(False)
        button_bg = OVERLAY_TRANSPARENT_COLOR if self.overlay_text_transparent else bg
        self.overlay_minimize_button = tk.Button(top_row, text="—", command=self.minimize_overlay, bg=button_bg, fg="#94a3b8", activebackground=button_bg, activeforeground="#f8fafc", relief="flat", bd=0, highlightthickness=0, font=("Segoe UI", 12), padx=8, pady=2, width=2, height=1, takefocus=0, cursor="hand2")
        self.overlay_minimize_button.pack(side="right")
        self.overlay_close_button = tk.Button(top_row, text="×", command=self.exit_application, bg=button_bg, fg="#f8fafc", activebackground=button_bg, activeforeground="#ffffff", relief="flat", bd=0, highlightthickness=0, font=("Segoe UI", 17, "bold"), padx=10, pady=2, width=2, height=1, takefocus=0, cursor="hand2")
        self.overlay_close_button.pack(side="right")
        text_bg = OVERLAY_TRANSPARENT_COLOR if self.overlay_text_transparent else bg
        value_row = tk.Frame(self.overlay_text, bg=text_bg)
        self.overlay_value_row = value_row
        value_row.pack(fill="x", padx=14, pady=(0, 0))
        self.overlay_labels["value"] = tk.Label(value_row, text="—", fg="#f8fafc", bg=text_bg, font=size["value_font"])
        self.overlay_labels["value"].pack(side="left")
        self.overlay_labels["trend"] = tk.Label(value_row, text="", fg="#38bdf8", bg=text_bg, font=size["trend_font"])
        self.overlay_labels["trend"].pack(side="left", padx=(5, 4))
        self.overlay_labels["unit"] = tk.Label(value_row, text=self.unit.get(), fg="#94a3b8", bg=text_bg, font=size["unit_font"])
        self.overlay_labels["unit"].pack(side="left", pady=(13, 0))
        self.overlay_labels["time"] = tk.Label(self.overlay_text, text="No data", fg="#cbd5e1", bg=text_bg, font=size["time_font"])
        self.overlay_labels["time"].pack(anchor="w", padx=16, pady=(0, 8))
        for widget in [self.overlay, self.overlay_text, top_row, value_row, *self.overlay_labels.values()]:
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag_overlay)
            widget.bind("<ButtonRelease-1>", self.save_overlay_position)
        self.apply_overlay_style()
        self.update_overlay_topmost()
        self.root.after_idle(self.update_overlay_topmost)
        self.update_overlay()

    def update_overlay(self):
        if not self.overlay or not self.overlay.winfo_exists() or not self.readings:
            return
        latest = self.readings[-1]
        age_minutes = max(0, (dt.datetime.now() - latest["time"]).total_seconds() / 60)
        warning = age_minutes >= WARNING_AFTER_MINUTES
        stale = age_minutes >= STALE_AFTER_MINUTES
        freshness_color = "#ef4444" if stale else "#f59e0b" if warning else self.glucose_color(latest["mgdl"])
        self.overlay_labels["value"].config(text=format_glucose(latest["mgdl"], self.unit.get()), fg=freshness_color)
        self.overlay_labels["trend"].config(text=latest.get("trend", ""))
        self.overlay_labels["unit"].config(text=self.unit.get())
        age_text = "just now" if age_minutes < 1 else f"{age_minutes:.0f} min ago"
        freshness_text = " • STALE" if stale else " • DELAYED" if warning else ""
        time_color = "#ef4444" if stale else "#f59e0b" if warning else "#cbd5e1"
        self.overlay_labels["time"].config(text=f"Reading {latest['time']:%H:%M} • {age_text}{freshness_text}", fg=time_color)

    def update_overlay_topmost(self):
        always_on_top = self.always_on_top.get()
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.attributes("-topmost", always_on_top)
            self.set_overlay_click_through(self.overlay, always_on_top)
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.attributes("-topmost", always_on_top)
            self.set_overlay_click_through(self.overlay_text, always_on_top)
        self.raise_overlay_layers()

    def start_drag(self, event):
        self.raise_overlay_layers()
        if self.overlay_locked.get():
            return
        self.drag_x = event.x_root - self.overlay_x
        self.drag_y = event.y_root - self.overlay_y

    def drag_overlay(self, event):
        if self.overlay_locked.get():
            return
        self.overlay_x = event.x_root - self.drag_x
        self.overlay_y = event.y_root - self.drag_y
        geometry = f"+{self.overlay_x}+{self.overlay_y}"
        self.overlay.geometry(geometry)
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.geometry(geometry)

    def save_overlay_position(self, event=None):
        self.keep_overlay_on_screen()
        self.settings["overlay_x"] = int(self.overlay_x)
        self.settings["overlay_y"] = int(self.overlay_y)
        save_settings(self.settings)


if __name__ == "__main__":
    app_root = tk.Tk()
    LibreViewOverlay(app_root)
    app_root.mainloop()
