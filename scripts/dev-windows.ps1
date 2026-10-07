param([switch] $SkipSetup)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $SkipSetup) { & (Join-Path $PSScriptRoot 'setup-windows.ps1') }
Push-Location (Join-Path $RepoRoot 'desktop')
try {
    & npm.cmd run tauri -- dev
    if ($LASTEXITCODE -ne 0) { throw "KAT desktop launch failed (exit $LASTEXITCODE)." }
} finally {
    Pop-Location
}
