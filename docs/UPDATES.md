# Releases and updates

Releases are published on the GitHub Releases page for this repository.

Each release should use a semantic version tag such as `v1.0.0` and include:

- `LibreDesktopOverlay-Setup.exe` — recommended installer.
- `LibreDesktopOverlay.exe` — portable executable.
- `README - Install.txt` — short end-user instructions.

The source repository contains the Python source, tests, build scripts, installer definition, and documentation. Generated `build`, `dist`, and `standalone` folders are excluded from source commits; their files are release assets instead.

Future in-app update checking can compare the application version with the latest public GitHub Release, download the installer asset, close the running application, and start the installer.
