# Releases and updates

Releases are published on the GitHub Releases page for this repository.

Each release should use a semantic version tag such as `v1.0.0` and include:

- `LibreDesktopOverlay-Setup.exe` — recommended installer.
- `LibreDesktopOverlay.exe` — portable executable.
- `README - Install.txt` — short end-user instructions.

## v1.0.34

- Restored the overlay’s transparent color key after enabling layered click-through mode.

## v1.0.33

- Fixed cross-process click-through by applying the required layered-window input style while preserving the overlay’s alpha rendering.

## v1.0.32

- Fixed click-through for applications in other Windows processes while preserving overlay rendering.

## v1.0.31

- Fixed a 64-bit Windows callback-pointer crash when enabling click-through mode.

## v1.0.30

- Fixed click-through input handling for the always-on-top overlay.

## v1.0.29

- Fixed black rendering introduced by the Windows click-through overlay style.

## v1.0.28

- Fixed the saved **Always on top** setting during startup.
- Added click-through behavior while **Always on top** is enabled.

## v1.0.21

- Added local Juggluco live readings over the trusted home network.
- Added the **Connect Juggluco** form with phone IP/hostname, port, optional API secret, connection testing, and secure secret storage.
- Clarified the Juggluco setup instructions, including what to enter in **Phone IP / hostname**.

The source repository contains the Python source, tests, build scripts, installer definition, and documentation. Generated `build`, `dist`, and `standalone` folders are excluded from source commits; their files are release assets instead.

The **Update app** button compares the application version with the latest public GitHub Release, downloads only the repository's HTTPS installer asset, closes the running application, and starts the installer. The installer launches the newly installed application from its normal installation folder when it finishes. A user can also update manually from the Releases page.

The installer uses an unpacked application bundle so startup and update relaunches do not depend on extracting the installed copy into a temporary `_MEI` folder. The portable release remains a single executable.

By default, the application also performs one update check shortly after startup. Disable **Check for updates on startup** when automatic checks are not wanted. The About window shows the installed version and links to the release page.

The overlay close button has a larger click area and remains usable when the overlay is locked.

The main window is vertically scrollable at smaller sizes. Food and insulin timeline markers are placed on the glucose line at the nearest reading and retain hover details.

Manage events can edit existing food and insulin entries as well as delete them.

