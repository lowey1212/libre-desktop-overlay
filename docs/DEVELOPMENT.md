# Development

## Requirements

- Windows 10 or newer.
- Python 3.11 or newer.
- Internet access for package installation and Gluroo connections.

Install dependencies and run the tests:

```powershell
python -m pip install -r requirements.txt
python -m unittest -v
```

## Build

Run `build_windows.ps1` from Windows. It creates the standalone executable and, when Inno Setup is installed, the installer under `standalone\`.

The packaged application uses PyInstaller in windowed mode and includes Python, Tkinter, requests, keyring, Pillow, and pystray. Overlay positions are clamped against the Windows virtual desktop so disconnected monitors and common DPI changes do not leave the overlay inaccessible.

## Data source

Gluroo Global Connect is the preferred near-live source. LibreView CSV import remains available as a historical/local fallback. The application polls the cloud source at the selected 30-, 60-, or 120-second interval and displays timestamps, diagnostics, and stale-data warnings.

Food and insulin timeline events are stored locally in `events.json`; the editable food reference list is stored in `foods.json`. The export layer keeps timestamped readings and events together without including Gluroo credentials or making treatment recommendations. Optional FoodData Central searches use a user-supplied API key from Windows Credential Manager.

The bundled UK food database is generated from the official [CoFID 2021 workbook](https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid). To refresh it after downloading a newer workbook, run:

```powershell
python .\tools\import_cofid.py .\path\to\CoFID.xlsx .\data\uk_cofid_foods.json
```

The generated file contains only food names, carbohydrate values, serving defaults, and CoFID identifiers; it does not contain Gluroo or LibreView credentials.
