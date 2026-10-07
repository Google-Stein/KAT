param()
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

if (-not (Test-Path $Python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -c 'import sys; sys.exit(sys.version_info < (3, 12))'
        Assert-Exit 'Python version check'
        & py -3 -m venv (Join-Path $CoreRoot '.venv')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -c 'import sys; sys.exit(sys.version_info < (3, 12))'
        Assert-Exit 'Python version check'
        & python -m venv (Join-Path $CoreRoot '.venv')
    } else {
        throw 'Install Python 3.12+ with the Python launcher, then run setup again.'
    }
    Assert-Exit 'Python virtual environment creation'
}
& $Python -c 'import sys; sys.exit(sys.version_info < (3, 12))'
Assert-Exit 'Virtual environment version check'
if (-not (Test-Path $Uv)) {
    # Keep uv outside the dependency-managed Core environment so sync cannot
    # remove its own running executable (which Windows locks).
    & $Python -m venv $UvRoot
    Assert-Exit 'Isolated setup tooling environment creation'
    & $UvPython -m pip install 'uv>=0.8,<1'
    Assert-Exit 'uv installation'
}
& $Uv sync --project $CoreRoot --frozen --group dev
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
