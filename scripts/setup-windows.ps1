param([string] $PythonExecutable = "")
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$CoreRoot = Join-Path $RepoRoot 'core'
$Python = Join-Path $CoreRoot '.venv\Scripts\python.exe'
$UvRoot = Join-Path $RepoRoot '.local\tools\uv'
$UvPython = Join-Path $UvRoot 'Scripts\python.exe'
$Uv = Join-Path $UvRoot 'Scripts\uv.exe'

function Assert-Exit([string] $Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)." }
}

function Assert-Python312([string] $Executable) {
    & $Executable -c 'import sys; print("KAT build Python:", sys.version, "at", sys.executable); sys.exit(sys.version_info[:2] != (3, 12))'
    if ($LASTEXITCODE -ne 0) { throw "KAT 0.1 builds require Python 3.12.x. Incompatible environment: $Executable. Remove only core/.venv and rerun setup with -PythonExecutable pointing to Python 3.12." }
}

if ($PythonExecutable) {
    Assert-Python312 $PythonExecutable
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'
    if ($LASTEXITCODE -eq 0) { $PythonExecutable = (Get-Command python).Source }
}
if (-not $PythonExecutable -and (Get-Command py -ErrorAction SilentlyContinue)) {
    $PythonExecutable = & py -3.12 -c 'import sys; print(sys.executable)'
    Assert-Exit 'Python 3.12 launcher selection'
}
if (-not $PythonExecutable) { throw 'Install Python 3.12.x or pass -PythonExecutable with its full path.' }
Assert-Python312 $PythonExecutable
if (-not (Test-Path $Python)) {
    & $PythonExecutable -m venv (Join-Path $CoreRoot '.venv')
    Assert-Exit 'Python virtual environment creation'
}
Assert-Python312 $Python
if (-not (Test-Path $Uv)) {
    # Keep uv outside the dependency-managed Core environment so sync cannot
    # remove its own running executable (which Windows locks).
    & $Python -m venv $UvRoot
    Assert-Exit 'Isolated setup tooling environment creation'
    & $UvPython -m pip install 'uv>=0.8,<1'
    Assert-Exit 'uv installation'
}
& $Uv sync --project $CoreRoot --python $Python --frozen --group dev
Assert-Exit 'Locked Python dependency installation'

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw 'Install Rust stable via rustup and Microsoft C++ Build Tools before starting Tauri.'
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 24 LTS before starting Tauri.'
}
& node -e "const [major,minor]=process.versions.node.split('.').map(Number); if(!((major===22 && minor>=12) || major===24 || major>=26)) { console.error('Use Node.js 24 LTS, or a supported Node.js 22.12+/26+ release'); process.exit(1); }"
Assert-Exit 'Node.js version check'
Push-Location (Join-Path $RepoRoot 'desktop')
try {
    & npm.cmd ci
    Assert-Exit 'Locked desktop dependency installation'
} finally {
    Pop-Location
}
Write-Host 'KAT dependencies are ready. Configure OPENAI_API_KEY in your environment or root .env, then run scripts/dev-windows.ps1.'
