param([switch] $SkipSetup, [switch] $NoBundle, [string] $PythonExecutable = "")
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot 'core\.venv\Scripts\python.exe'
$BuildRoot = Join-Path $RepoRoot '.local\build\pyinstaller'
$BinaryRoot = Join-Path $RepoRoot 'desktop\src-tauri\binaries'
if (-not $SkipSetup) { & (Join-Path $PSScriptRoot 'setup-windows.ps1') -PythonExecutable $PythonExecutable }
if (-not (Test-Path $Python)) { throw 'Core virtual environment is missing. Run scripts/setup-windows.ps1.' }
& $Python -c 'import sys; print("PyInstaller runtime:", sys.version, "at", sys.executable); sys.exit(sys.version_info[:2] != (3, 12))'
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller packaging requires the supported Python 3.12.x Core environment.' }
New-Item -ItemType Directory -Force -Path $BuildRoot, $BinaryRoot | Out-Null

& $Python -m PyInstaller --noconfirm --clean --onedir --name kat-core `
    --paths (Join-Path $RepoRoot 'core\src') `
    --collect-all agents --collect-all openai `
    --collect-submodules uvicorn --recursive-copy-metadata openai-agents `
    --distpath $BinaryRoot --workpath (Join-Path $BuildRoot 'work') `
    --specpath $BuildRoot (Join-Path $PSScriptRoot 'core_entry.py')
if ($LASTEXITCODE -ne 0) { throw "KAT Core packaging failed (exit $LASTEXITCODE)." }
if (-not (Test-Path (Join-Path $BinaryRoot 'kat-core\kat-core.exe'))) { throw 'PyInstaller did not produce kat-core/kat-core.exe.' }

Push-Location (Join-Path $RepoRoot 'desktop')
try {
    if ($NoBundle) {
        & npm.cmd run tauri -- build --no-bundle -- --locked
    } else {
        & npm.cmd run tauri -- build -- --locked
    }
    if ($LASTEXITCODE -ne 0) { throw "KAT Windows installer build failed (exit $LASTEXITCODE)." }
} finally {
    Pop-Location
}
if ($NoBundle) {
    Write-Host 'Windows desktop executable and resources created under desktop/src-tauri/target/release/.'
} else {
    Write-Host 'Windows installer created under desktop/src-tauri/target/release/bundle/nsis/.'
}
