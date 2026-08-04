@echo off
if /i not "%~1"=="/hidden" (
    wscript.exe "%~dp0Start LibreView Overlay.vbs"
    exit /b 0
)
cd /d "%~dp0"
python -c "import keyring, requests, pystray, PIL" >nul 2>&1
if errorlevel 1 (
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        msg * "Libre Desktop requirements could not be installed. Check your internet connection."
        exit /b 1
    )
)
pythonw.exe libreview_overlay.py
