# Installation

## Recommended: installer

Download `LibreDesktopOverlay-Setup.exe` from the latest GitHub Release and double-click it. The installer adds Start-menu and desktop shortcuts and registers a normal Windows uninstall entry.

If Windows SmartScreen appears, select **More info** and then **Run anyway**. The first releases are not digitally signed, so this warning is expected.

## Portable version

Download `LibreDesktopOverlay.exe` from the latest GitHub Release and double-click it. Python does not need to be installed separately.

## First connection

1. Open the application.
2. Select **Connect Gluroo**.
3. In Gluroo, open **Menu → Settings → Gluroo Global Connect Nightscout**.
4. Paste the complete URL or the JSON-style URL/token/header block into the application.
5. Enable secure remembering only if automatic reconnection is wanted.

The application does not ask for a LibreView or Gluroo account password. Remembered Gluroo connection details use Windows Credential Manager.

## Startup behaviour

Use **Start with overlay** to show the reading automatically. Use **Start hidden in tray** to keep the main window out of the taskbar. The overlay’s **—** button hides it temporarily; **×** closes the complete application.
