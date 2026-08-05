$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
$cofidDataPath = Join-Path $projectRoot "data\uk_cofid_foods.json"

python -m pip install -r .\requirements.txt
python -m pip install "pyinstaller>=6,<7"

python -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --windowed `
    --name LibreDesktopOverlay `
    --distpath .\standalone `
    --workpath .\build\LibreDesktopOverlay `
    --specpath .\build `
    --add-data "$cofidDataPath;data" `
    --hidden-import keyring.backends.Windows `
    --collect-submodules keyring `
    .\libreview_overlay.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

# Build the installed application as an onedir bundle. The portable release
# remains a single executable, but the installed copy avoids one-file runtime
# extraction into %TEMP% during updates and startup.
python -m PyInstaller `
    --clean `
    --noconfirm `
    --onedir `
    --windowed `
    --name LibreDesktopOverlay `
    --distpath .\build\installer-dist `
    --workpath .\build\LibreDesktopOverlay-installer `
    --specpath .\build `
    --add-data "$cofidDataPath;data" `
    --hidden-import keyring.backends.Windows `
    --collect-submodules keyring `
    .\libreview_overlay.py

if ($LASTEXITCODE -ne 0) {
    throw "Installer bundle build failed with exit code $LASTEXITCODE"
}

Copy-Item -LiteralPath .\LICENSE -Destination .\standalone\LICENSE -Force

Write-Host "Built: $projectRoot\standalone\LibreDesktopOverlay.exe"

$innoCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:LOCALAPPDATA} "Programs\Inno Setup 6\ISCC.exe")
)
$innoCompiler = $innoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($innoCompiler) {
    & $innoCompiler .\installer.iss
    Write-Host "Built: $projectRoot\standalone\LibreDesktopOverlay-Setup.exe"
} else {
    Write-Warning "Inno Setup is not installed; skipped installer creation."
}
