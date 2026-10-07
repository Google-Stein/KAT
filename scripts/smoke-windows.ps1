param(
  [string]$Executable = "",
  [int]$TimeoutSeconds = 45
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Executable) {
  $Executable = Join-Path $repo "desktop/src-tauri/target/release/kat-desktop.exe"
}
if (-not (Test-Path $Executable)) { throw "Desktop executable not found: $Executable" }
$app = $null
$children = @()

function Wait-KatReady($process) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    Start-Sleep -Milliseconds 300
    $process.Refresh()
    if ($process.HasExited) { throw "Desktop exited during startup (code $($process.ExitCode))." }
    $owned = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($process.Id)" |
      Where-Object { $_.Name -eq "kat-core.exe" })
    if ($process.MainWindowHandle -ne 0 -and $owned.Count -gt 0) { return $owned }
  } while ((Get-Date) -lt $deadline)
  throw "Desktop did not create its window and owned Core before timeout."
}

function Assert-KatStopped($owned) {
  $deadline = (Get-Date).AddSeconds(8)
  do {
    $alive = @($owned | Where-Object {
      Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    })
    $probe = [System.Net.Sockets.TcpClient]::new()
    try {
      try { $probe.Connect("127.0.0.1", 42800) } catch [System.Net.Sockets.SocketException] { }
      $portOpen = $probe.Connected
    } finally { $probe.Dispose() }
    if ($alive.Count -eq 0 -and -not $portOpen) { return }
    Start-Sleep -Milliseconds 250
  } while ((Get-Date) -lt $deadline)
  throw "Desktop shutdown left an owned Core process or port 42800 open."
}

try {
  $app = Start-Process -FilePath $Executable -PassThru
  $children = @(Wait-KatReady $app)
  # Native retains its owned Core process only after authenticated health succeeds.
  Write-Output "PASS: packaged desktop window and authenticated Core startup."
  if (-not $app.CloseMainWindow()) { throw "Could not request normal desktop shutdown." }
  if (-not $app.WaitForExit(15000)) { throw "Desktop did not shut down cleanly." }
  Assert-KatStopped $children
  Write-Output "PASS: normal window close stopped the owned Core."

  $app = Start-Process -FilePath $Executable -PassThru
  $children = @(Wait-KatReady $app)
  Stop-Process -Id $app.Id -Force
  if (-not $app.WaitForExit(15000)) { throw "Forced desktop exit did not complete." }
  Assert-KatStopped $children
  Write-Output "PASS: forced desktop exit stopped Core through the Windows Job Object."
} finally {
  if ($app -and -not $app.HasExited) { Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue }
  foreach ($child in $children) {
    Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
