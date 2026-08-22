# Installation

## Recommended: installer

Download `LibreDesktopOverlay-Setup.exe` from the latest GitHub Release and double-click it. The installer adds Start-menu and desktop shortcuts and registers a normal Windows uninstall entry.

If Windows SmartScreen appears, select **More info** and then **Run anyway**. The first releases are not digitally signed, so this warning is expected.

## Portable version

Download `LibreDesktopOverlay.exe` from the latest GitHub Release and double-click it. Python does not need to be installed separately.

## First connection: recommended local Juggluco

1. Open the application and select **Live source → Juggluco — Local**.
2. In Juggluco open **Settings → Exchange data → Web server** and enable it.
3. Unset **Local only**, use port **17580**, and ensure the phone and PC are on the same local network.
4. Select **Connect Juggluco**. In **Phone IP / hostname**, enter the phone's Wi-Fi IP address or hostname, such as `192.168.1.42`—not the PC's IP address or a phone number.
5. Leave **Port** as `17580`. Leave **API secret** blank unless you configured one in Juggluco; otherwise enter the same secret here. Select **Test connection**, then **Connect** if it succeeds.
6. Enable secure remembering only if automatic reconnection is wanted. Do not port-forward the Juggluco server.

If the test fails, confirm that Juggluco's web server is still enabled, the phone and PC are on the same non-guest network, and the phone's IP address has not changed. Never expose port 17580 to the public internet.

For current Libre 2/2+ and Libre 3/3+ sensor setup, follow the [official Juggluco documentation](https://www.juggluco.nl/Juggluco/). The sensor-generation setup differs, and Abbott's app and Juggluco may interfere over Bluetooth when both attempt to use the same sensor.

## Optional Gluroo connection

Select **Live source → Gluroo — Cloud**, then connect using the existing Gluroo Global Connect URL/token/header flow.

The application does not ask for a LibreView or Gluroo account password. Remembered Gluroo connection details use Windows Credential Manager.

> Libre Desktop Overlay is an unofficial, independently developed Windows companion display. It connects to a user-authorised Gluroo Global Connect/Nightscout-compatible feed. It is not affiliated with, endorsed by or supported by Gluroo, Abbott or the Nightscout project.
>
> This application is a secondary convenience display only. Verify readings using the official CGM application before making insulin or treatment decisions.

## Startup behaviour

Use **Start with overlay** to show the reading automatically. Use **Start hidden in tray** to keep the main window out of the taskbar. Use **Start with Windows** to launch the app automatically when you sign in to Windows. This is registered for the current Windows user only and does not require administrator access. The overlay’s **—** button hides it temporarily; **×** closes the complete application.

## Preferences and recovery

Choose a 30-, 60-, or 120-second refresh interval. The main window can check for new releases automatically at startup; this can be disabled with **Check for updates on startup**. **Reset position** returns the overlay to a visible position if a monitor is disconnected or Windows changes display scaling.

Use **Export appearance** and **Import appearance** to transfer colour, opacity, size, position, units, locking, and always-on-top preferences. Appearance files do not contain Gluroo connection details.

## Interface screenshots

![Libre Desktop main window](screenshots/main-window.png)

![Add food dialog](screenshots/add-food.png)

![Log insulin dialog](screenshots/log-insulin.png)

![Food database](screenshots/food-database.png)

![Recorded timeline events](screenshots/timeline-events.png)

## Food and insulin records

Use **Add food** or **Log insulin** to place timestamped events on the glucose graph. If a food is not listed, use **Add food to list** to save its name, serving, and carbohydrates for future entries. Use **Manage events** to select an entry and edit it, or double-click it. The app records the food/portion/carbohydrates or insulin type/units exactly as entered and does not calculate or recommend doses.

Use **Food database** to search the bundled UK [CoFID 2021 dataset](https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid) offline. Its values are generally carbohydrates per 100 g, so check the serving size and adjust it when logging food. You can edit the local list or select USA to search the official [USDA FoodData Central API](https://fdc.nal.usda.gov/api-guide/) with your own API key. The key is stored in Windows Credential Manager. **Export data** creates a CSV or JSON timeline for review with your GP, nurse, or official medical software.

The project is distributed under the [Libre Desktop Overlay Free Use Licence](../LICENSE). Modified or redistributed versions must remain free of charge and must clearly acknowledge the original project as **“Based on Libre Desktop Overlay by lowey1212”** with a link to [the original project](https://github.com/lowey1212/libre-desktop-overlay).
