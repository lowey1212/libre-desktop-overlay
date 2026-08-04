$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

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
    --hidden-import keyring.backends.Windows `
    --collect-submodules keyring `
    .\libreview_overlay.py

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
