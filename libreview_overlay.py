import csv
import datetime as dt
import json
import os
import queue
import re
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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
)


FILE_REFRESH_MS = 60_000
CLOUD_REFRESH_MS = 60_000
WARNING_AFTER_MINUTES = 5
STALE_AFTER_MINUTES = 10
MGDL_PER_MMOLL = 18.0182
CREDENTIAL_SERVICE = "LibreView Desktop Overlay"
APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.cwd())) / "LibreViewDesktopOverlay"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"
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


def load_settings():
    defaults = {
        "unit": "mmol/L",
        "gluroo_remember": False,
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
    if "start_overlay" not in data:
        defaults["start_overlay"] = bool(defaults.get("overlay_enabled", False))
    return defaults


def save_settings(settings):
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


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
        self.readings = []
        self.csv_path = None
        self.last_modified = None
        self.data_source = None
        self.cloud_session = None
        self.cloud_busy = False
        self.provider_generation = 0
        self.worker_results = queue.Queue()
        self.login_window = None
        self.overlay = None
        self.overlay_text = None
        self.overlay_labels = {}
        self.overlay_value_row = None
        self.overlay_close_button = None
        self.overlay_minimize_button = None
        self.overlay_text_transparent = False
        self.overlay_x = int(self.settings.get("overlay_x", 30))
        self.overlay_y = int(self.settings.get("overlay_y", 30))
        self.tray_icon = None
        self.tray_thread = None
        self.exiting = False
        self.drag_x = 0
        self.drag_y = 0

        self.always_on_top = tk.BooleanVar(value=True)
        self.start_overlay = tk.BooleanVar(value=bool(self.settings.get("start_overlay", False)))
        self.overlay_enabled = tk.BooleanVar(value=self.start_overlay.get())
        self.overlay_color = tk.StringVar(value=self.settings.get("overlay_color", "Navy"))
        self.overlay_background_opacity = tk.IntVar(value=int(self.settings.get("overlay_background_opacity", 82)))
        self.overlay_number_opacity = tk.IntVar(value=int(self.settings.get("overlay_number_opacity", 100)))
        self.overlay_size = tk.StringVar(value=self.settings.get("overlay_size", "Medium"))
        self.overlay_locked = tk.BooleanVar(value=bool(self.settings.get("overlay_locked", False)))
        self.start_hidden = tk.BooleanVar(value=bool(self.settings.get("start_hidden", False)))
        self.unit = tk.StringVar(value=self.settings.get("unit", "mmol/L"))
        self.status = tk.StringVar(value="Connect Gluroo for near-live readings, or open a CSV.")

        self.build_main_ui()
        self.unit.trace_add("write", self.on_unit_change)
        self.overlay_color.trace_add("write", self.on_overlay_style_change)
        self.overlay_background_opacity.trace_add("write", self.on_overlay_style_change)
        self.overlay_number_opacity.trace_add("write", self.on_overlay_style_change)
        self.overlay_size.trace_add("write", self.on_overlay_size_change)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_main)
        self.root.bind("<Unmap>", self.handle_root_unmap, add="+")
        self.root.after(100, self.start_tray_icon)
        self.root.after(100, self.process_worker_results)
        self.root.after(FILE_REFRESH_MS, self.poll_file)
        self.root.after(CLOUD_REFRESH_MS, self.poll_cloud)
        self.root.after(30_000, self.refresh_freshness)
        self.root.after(500, self.try_auto_connect)
        if self.start_overlay.get():
            self.overlay_enabled.set(True)
            self.show_overlay()
        if self.start_hidden.get():
            self.root.after(250, self.minimize_main)

    def build_main_ui(self):
        header = tk.Frame(self.root, bg="#0b1220")
        header.pack(fill="x", padx=24, pady=(22, 10))
        tk.Label(header, text="Libre Desktop", fg="#f8fafc", bg="#0b1220", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(header, text="Near-live Gluroo display with a local CSV fallback", fg="#94a3b8", bg="#0b1220", font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 0))

        controls = tk.Frame(self.root, bg="#111827")
        controls.pack(fill="x", padx=24, pady=(4, 8))
        self.gluroo_button = tk.Button(controls, text="Connect Gluroo", command=self.open_gluroo_login, bg="#7c3aed", fg="white", activebackground="#6d28d9", relief="flat", padx=14, pady=8)
        self.gluroo_button.pack(side="left", padx=(12, 6), pady=12)
        tk.Button(controls, text="Open CSV", command=self.choose_file, bg="#475569", fg="white", activebackground="#334155", relief="flat", padx=14, pady=8).pack(side="left", padx=6, pady=12)
        tk.Button(controls, text="Show overlay", command=self.enable_overlay, bg="#16a34a", fg="white", activebackground="#15803d", relief="flat", padx=14, pady=8).pack(side="left", padx=6, pady=12)
        tk.Checkbutton(controls, text="Always on top", variable=self.always_on_top, command=self.update_overlay_topmost, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=12)
        tk.Checkbutton(controls, text="Lock overlay", variable=self.overlay_locked, command=self.toggle_overlay_lock, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=8)
        tk.Button(controls, text="Exit", command=self.exit_application, bg="#7f1d1d", fg="white", activebackground="#991b1b", relief="flat", padx=12, pady=8).pack(side="right", padx=8, pady=12)
        unit_box = ttk.Combobox(controls, textvariable=self.unit, values=["mmol/L", "mg/dL"], state="readonly", width=8)
        unit_box.pack(side="right", padx=14)
        tk.Label(controls, text="Units", fg="#94a3b8", bg="#111827").pack(side="right")

        style_bar = tk.Frame(self.root, bg="#111827")
        style_bar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(style_bar, text="Overlay colour", fg="#94a3b8", bg="#111827").pack(side="left", padx=(14, 6), pady=8)
        ttk.Combobox(style_bar, textvariable=self.overlay_color, values=["Navy", "Black", "Purple", "Forest", "Slate"], state="readonly", width=10).pack(side="left", pady=8)
        tk.Label(style_bar, text="Background", fg="#94a3b8", bg="#111827").pack(side="left", padx=(20, 6), pady=8)
        tk.Scale(style_bar, from_=35, to=100, orient="horizontal", variable=self.overlay_background_opacity, showvalue=True, length=105, bg="#111827", fg="#e5e7eb", troughcolor="#334155", highlightthickness=0, activebackground="#38bdf8").pack(side="left", pady=2)
        tk.Label(style_bar, text="Number", fg="#94a3b8", bg="#111827").pack(side="left", padx=(12, 6), pady=8)
        tk.Scale(style_bar, from_=35, to=100, orient="horizontal", variable=self.overlay_number_opacity, showvalue=True, length=105, bg="#111827", fg="#e5e7eb", troughcolor="#334155", highlightthickness=0, activebackground="#38bdf8").pack(side="left", pady=2)
        tk.Label(style_bar, text="Size", fg="#94a3b8", bg="#111827").pack(side="left", padx=(20, 6), pady=8)
        ttk.Combobox(style_bar, textvariable=self.overlay_size, values=list(OVERLAY_SIZES), state="readonly", width=9).pack(side="left", pady=8)

        startup_bar = tk.Frame(self.root, bg="#111827")
        startup_bar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(startup_bar, text="Startup", fg="#94a3b8", bg="#111827").pack(side="left", padx=(14, 6), pady=8)
        tk.Checkbutton(startup_bar, text="Start with overlay", variable=self.start_overlay, command=self.toggle_start_overlay, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=8)
        tk.Checkbutton(startup_bar, text="Start hidden in tray", variable=self.start_hidden, command=self.toggle_start_hidden, bg="#111827", fg="#e5e7eb", selectcolor="#111827", activebackground="#111827", activeforeground="#e5e7eb").pack(side="left", padx=8)

        status_bar = tk.Frame(self.root, bg="#0b1220")
        status_bar.pack(fill="x", padx=28, pady=(0, 10))
        tk.Label(status_bar, textvariable=self.status, fg="#cbd5e1", bg="#0b1220", anchor="w", font=("Segoe UI", 9)).pack(fill="x")

        self.current_card = tk.Frame(self.root, bg="#172033")
        self.current_card.pack(fill="x", padx=24, pady=(0, 14))
        self.current_value = tk.Label(self.current_card, text="—", fg="#f8fafc", bg="#172033", font=("Segoe UI", 44, "bold"))
        self.current_value.pack(side="left", padx=(22, 4), pady=18)
        self.current_trend = tk.Label(self.current_card, text="", fg="#38bdf8", bg="#172033", font=("Segoe UI", 30, "bold"))
        self.current_trend.pack(side="left", padx=(0, 8))
        self.current_unit = tk.Label(self.current_card, text=self.unit.get(), fg="#94a3b8", bg="#172033", font=("Segoe UI", 13))
        self.current_unit.pack(side="left", pady=(26, 0))
        self.current_time = tk.Label(self.current_card, text="No data loaded", fg="#cbd5e1", bg="#172033", justify="right", font=("Segoe UI", 11))
        self.current_time.pack(side="right", padx=22)

        graph_frame = tk.Frame(self.root, bg="#111827")
        graph_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        tk.Label(graph_frame, text="Recent glucose history", fg="#f8fafc", bg="#111827", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        self.canvas = tk.Canvas(graph_frame, bg="#111827", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", lambda event: self.draw_graph())

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

    def try_auto_connect(self):
        if self.settings.get("gluroo_remember"):
            global_connect_url = get_vault_password("gluroo-global-connect")
            if global_connect_url:
                self.start_gluroo_connection(global_connect_url, True, None)

    def start_gluroo_connection(self, global_connect_url, remember, login_window):
        self.provider_generation += 1
        generation = self.provider_generation
        self.cloud_busy = True
        self.gluroo_button.config(state="disabled", text="Connecting…")
        self.status.set("Connecting to the Gluroo live feed…")

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
                self.worker_results.put(("connected", generation, session, cloud_readings, remember, saved_ok, login_window))
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
                if kind == "connected":
                    _, generation, session, cloud_readings, remember, saved_ok, login_window = result
                    if generation != self.provider_generation:
                        continue
                    self.cloud_busy = False
                    self.cloud_session = session
                    self.data_source = "cloud"
                    self.readings = [
                        {"time": item.time, "mgdl": item.mgdl, "trend": item.trend}
                        for item in cloud_readings
                    ]
                    self.settings.update({"unit": self.unit.get(), "gluroo_remember": remember and saved_ok})
                    save_settings(self.settings)
                    if login_window and login_window.winfo_exists():
                        login_window.destroy()
                    self.gluroo_button.config(state="normal", text="Reconnect Gluroo")
                    suffix = " • secure auto-connect unavailable" if remember and not saved_ok else ""
                    self.status.set(f"Near-live via Gluroo • checked {dt.datetime.now():%H:%M:%S}{suffix}")
                    self.update_display()
                    if self.overlay_enabled.get() or login_window or self.start_overlay.get():
                        self.enable_overlay()
                elif kind == "connect_error":
                    _, generation, error_message, login_window = result
                    if generation != self.provider_generation:
                        continue
                    self.cloud_busy = False
                    self.gluroo_button.config(state="normal", text="Connect Gluroo")
                    self.status.set(error_message)
                    if login_window and login_window.winfo_exists():
                        login_window.destroy()
                    messagebox.showerror("Gluroo connection failed", error_message, parent=self.root)
                elif kind == "refreshed":
                    _, generation, cloud_readings = result
                    if generation != self.provider_generation or self.data_source != "cloud":
                        continue
                    self.cloud_busy = False
                    self.readings = [
                        {"time": item.time, "mgdl": item.mgdl, "trend": item.trend}
                        for item in cloud_readings
                    ]
                    self.status.set(f"Near-live via Gluroo • checked {dt.datetime.now():%H:%M:%S}")
                    self.update_display()
                elif kind == "refresh_error":
                    _, generation, error_message = result
                    if generation != self.provider_generation or self.data_source != "cloud":
                        continue
                    self.cloud_busy = False
                    self.status.set(f"Refresh failed; keeping last reading • {error_message}")
                    self.update_display()
        except queue.Empty:
            pass
        self.root.after(100, self.process_worker_results)

    def poll_cloud(self):
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
        self.root.after(CLOUD_REFRESH_MS, self.poll_cloud)

    def choose_file(self):
        path = filedialog.askopenfilename(title="Select LibreView CSV export", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            csv_readings = load_libreview_csv(path)
            self.provider_generation += 1
            self.cloud_busy = False
            self.readings = csv_readings
            self.csv_path = path
            self.last_modified = os.path.getmtime(path)
            self.data_source = "csv"
            self.status.set(f"CSV fallback • loaded {len(self.readings):,} readings • watching for changes")
            self.update_display()
            if self.overlay_enabled.get():
                self.show_overlay()
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not load LibreView data", str(error))

    def poll_file(self):
        if self.csv_path and self.data_source == "csv":
            try:
                modified = os.path.getmtime(self.csv_path)
                if self.last_modified != modified:
                    self.load_file(self.csv_path)
            except OSError:
                pass
        self.root.after(FILE_REFRESH_MS, self.poll_file)

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

    def toggle_start_overlay(self):
        self.settings["start_overlay"] = self.start_overlay.get()
        save_settings(self.settings)

    def toggle_start_hidden(self):
        self.settings["start_hidden"] = self.start_hidden.get()
        save_settings(self.settings)

    def apply_overlay_style(self):
        if not self.overlay or not self.overlay.winfo_exists():
            return
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
        return "#f8fafc"

    def draw_graph(self):
        self.canvas.delete("all")
        if not self.readings:
            self.canvas.create_text(300, 100, text="Connect Gluroo or load a CSV to see the graph", fill="#94a3b8", font=("Segoe UI", 12))
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
        top_row = tk.Frame(self.overlay_text, bg=OVERLAY_TRANSPARENT_COLOR if self.overlay_text_transparent else bg, height=22)
        top_row.pack(fill="x", padx=6, pady=(2, 0))
        top_row.pack_propagate(False)
        button_bg = OVERLAY_TRANSPARENT_COLOR if self.overlay_text_transparent else bg
        self.overlay_minimize_button = tk.Button(top_row, text="—", command=self.minimize_overlay, bg=button_bg, fg="#94a3b8", activebackground=button_bg, activeforeground="#f8fafc", relief="flat", bd=0, highlightthickness=0, font=("Segoe UI", 10), padx=3, pady=0)
        self.overlay_minimize_button.pack(side="right")
        self.overlay_close_button = tk.Button(top_row, text="×", command=self.exit_application, bg=button_bg, fg="#94a3b8", activebackground=button_bg, activeforeground="#f8fafc", relief="flat", bd=0, highlightthickness=0, font=("Segoe UI", 12), padx=3, pady=0)
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
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.attributes("-topmost", self.always_on_top.get())
        if self.overlay_text and self.overlay_text.winfo_exists():
            self.overlay_text.attributes("-topmost", self.always_on_top.get())
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
        self.settings["overlay_x"] = int(self.overlay_x)
        self.settings["overlay_y"] = int(self.overlay_y)
        save_settings(self.settings)


if __name__ == "__main__":
    app_root = tk.Tk()
    LibreViewOverlay(app_root)
    app_root.mainloop()
