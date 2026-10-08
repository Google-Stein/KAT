param([string]$Installer = '')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = Split-Path -Parent $PSScriptRoot
$root = Join-Path $repo '.local/windows-install'
$install = Join-Path $root 'KAT App'
$data = Join-Path $env:LOCALAPPDATA 'com.kat.assistant'
$database = Join-Path $data 'kat.sqlite3'
$python = Join-Path $repo 'core/.venv/Scripts/python.exe'
if (-not $Installer) {
  $packages = @(Get-ChildItem (Join-Path $repo 'desktop/src-tauri/target/release/bundle/nsis') -Filter '*-setup.exe')
  if ($packages.Count -ne 1) { throw '[installer] Expected exactly one NSIS installer.' }
  $Installer = $packages[0].FullName
}
if (Test-Path $install) { throw '[installer] Test installation directory already exists; refusing to overwrite.' }
New-Item -ItemType Directory -Force -Path $root | Out-Null
$setup = Start-Process -FilePath $Installer -ArgumentList "/S /D=$install" -Wait -PassThru
if ($setup.ExitCode -ne 0) { throw "[installer] Installation failed: $($setup.ExitCode)." }
$executables = @(Get-ChildItem $install -Filter '*.exe' | Where-Object { $_.Name -notmatch 'uninstall' })
if ($executables.Count -ne 1) { throw '[installer] Installed desktop executable not found or ambiguous.' }
$exe = $executables[0].FullName
if (-not (Test-Path (Join-Path $install 'binaries/kat-core/kat-core.exe'))) { throw '[installer] Packaged Core resources missing from installed application.' }
Write-Output 'PASS: current-user NSIS installation and Core resources.'
& (Join-Path $PSScriptRoot 'smoke-windows.ps1') -Executable $exe -DiagnosticsDirectory (Join-Path $repo '.local/windows-smoke/installed')
if (-not (Test-Path $database)) { throw '[persistence] Installed Core did not create its database.' }
# Write an isolated smoke conversation through the real Store after Core has stopped.
# Never remove or overwrite existing user conversations.
$env:KAT_INSTALL_SMOKE_DATABASE = $database
& $python -c 'import os; from pathlib import Path; from kat_core.storage import Store; s=Store(Path(os.environ["KAT_INSTALL_SMOKE_DATABASE"])); c=s.create_session("Installer persistence smoke"); s.add_message(c.id,"user","Installer persistence marker"); s.close()'
if ($LASTEXITCODE -ne 0) { throw '[persistence] Failed to write smoke conversation.' }
& (Join-Path $PSScriptRoot 'smoke-windows.ps1') -Executable $exe -DiagnosticsDirectory (Join-Path $repo '.local/windows-smoke/reinstalled-launch')
& $python -c 'import os; from pathlib import Path; from kat_core.storage import Store; s=Store(Path(os.environ["KAT_INSTALL_SMOKE_DATABASE"])); c=[c for c in s.sessions() if c.title=="Installer persistence smoke"]; assert c and any(m.content=="Installer persistence marker" for m in s.messages(c[0].id)); s.close()'
if ($LASTEXITCODE -ne 0) { throw '[persistence] Conversation did not survive installed restart.' }
Write-Output 'PASS: installed application relaunch preserves conversation data.'
$uninstallers = @(Get-ChildItem $install -Filter '*uninstall*.exe')
if ($uninstallers.Count -ne 1) { throw '[uninstaller] Cannot locate installed uninstaller.' }
$uninstall = Start-Process -FilePath $uninstallers[0].FullName -ArgumentList '/S' -Wait -PassThru
if ($uninstall.ExitCode -ne 0) { throw "[uninstaller] Uninstall failed: $($uninstall.ExitCode)." }
$deadline = (Get-Date).AddSeconds(15)
while ((Test-Path $exe) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 200 }
if (Test-Path $exe) { throw '[uninstaller] Application executable remains after uninstall.' }
if (-not (Test-Path $database)) { throw '[uninstaller] Uninstall unexpectedly removed conversation data.' }
& $python -c 'import os,sqlite3; c=sqlite3.connect(os.environ["KAT_INSTALL_SMOKE_DATABASE"]); assert c.execute("SELECT count(*) FROM messages WHERE content=?",("Installer persistence marker",)).fetchone()[0]>=1; assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; c.close()'
if ($LASTEXITCODE -ne 0) { throw '[uninstaller] Preserved database was not intact.' }
Remove-Item Env:KAT_INSTALL_SMOKE_DATABASE
Write-Output 'PASS: uninstall removes application and preserves intact local user data.'
