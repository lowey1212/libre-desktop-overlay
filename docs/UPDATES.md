# Releases and updates

Releases are published on the GitHub Releases page for this repository.

Each release should use a semantic version tag such as `v1.0.0` and include:

- `LibreDesktopOverlay-Setup.exe` — recommended installer.
- `LibreDesktopOverlay.exe` — portable executable.
- `README - Install.txt` — short end-user instructions.

The source repository contains the Python source, tests, build scripts, installer definition, and documentation. Generated `build`, `dist`, and `standalone` folders are excluded from source commits; their files are release assets instead.

The **Update app** button compares the application version with the latest public GitHub Release, downloads only the repository's HTTPS installer asset, closes the running application, and starts the installer. The installer launches the newly installed application from its normal installation folder when it finishes. A user can also update manually from the Releases page.

The installer uses an unpacked application bundle so startup and update relaunches do not depend on extracting the installed copy into a temporary `_MEI` folder. The portable release remains a single executable.

By default, the application also performs one update check shortly after startup. Disable **Check for updates on startup** when automatic checks are not wanted. The About window shows the installed version and links to the release page.

The overlay close button has a larger click area and remains usable when the overlay is locked.

The main window is vertically scrollable at smaller sizes. Food and insulin timeline markers are placed on the glucose line at the nearest reading and retain hover details.
