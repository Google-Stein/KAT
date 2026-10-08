param(
  [string]$Executable = "",
  [int]$TimeoutSeconds = 45,
  [string]$DiagnosticsDirectory = ""
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Executable) { $Executable = Join-Path $repo "desktop/src-tauri/target/release/kat-desktop.exe" }
if (-not $DiagnosticsDirectory) { $DiagnosticsDirectory = Join-Path $repo ".local/windows-smoke" }
$logs = Join-Path $env:LOCALAPPDATA "com.kat.assistant/logs"
$desktopLog = Join-Path $logs "desktop.log"
$app = $null
$children = @()
$startedMilliseconds = 0L
New-Item -ItemType Directory -Force -Path $DiagnosticsDirectory | Out-Null

function Get-KatListener {
  @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 42800 -State Listen -ErrorAction SilentlyContinue)
}
function Get-StartupEvidence($process) {
  if (-not (Test-Path $desktopLog)) { return @() }
  @(Get-Content $desktopLog | Where-Object {
    $_ -match "timestamp=(\d+) desktop_pid=$($process.Id) " -and [long]$Matches[1] -ge $script:startedMilliseconds
  })
}
function Fail-Kat([string]$Category, [string]$Detail) { throw "[$Category] $Detail" }

function Wait-KatReady($process) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    Start-Sleep -Milliseconds 300
    $process.Refresh()
    if ($process.HasExited) { Fail-Kat "desktop-process" "Desktop exited during startup (code $($process.ExitCode))." }
    $evidence = @(Get-StartupEvidence $process)
    $script:children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($process.Id)" |
      Where-Object { $_.Name -eq "kat-core.exe" })
    if ($script:children.Count -gt 1) { Fail-Kat "process-topology" "Multiple direct Core children of desktop $($process.Id)." }
    $failure = @($evidence | Where-Object { $_ -match 'stage=core_failed ' })
    if ($failure.Count -gt 0) {
      $category = if ($failure[-1] -match 'credential|become ready|health check') { "authenticated-readiness" }
        elseif ($failure[-1] -match 'port|127\.0\.0\.1:42800') { "port-lifecycle" }
        else { "core-child-startup" }
      Fail-Kat $category $failure[-1]
    }
    if (@($evidence | Where-Object { $_ -match 'stage=window_failed ' }).Count -gt 0) {
      Fail-Kat "window-creation" "Native WebView window initialization failed."
    }
    $ready = @($evidence | Where-Object { $_ -match 'stage=core_ready core_pid=(\d+) authenticated=true port=42800' })
    if ($ready.Count -gt 0) {
      $null = $ready[-1] -match 'core_pid=(\d+)'
      $reportedCorePid = [int]$Matches[1]
      if ($script:children.Count -ne 1 -or $script:children[0].ProcessId -ne $reportedCorePid) {
        Fail-Kat "process-topology" "Authenticated Core PID $reportedCorePid is not the desktop's single direct child."
      }
      $listeners = @(Get-KatListener)
      if ($listeners.Count -ne 1 -or $listeners[0].OwningProcess -ne $reportedCorePid) {
        Fail-Kat "port-lifecycle" "Port 42800 is not exclusively owned by authenticated Core PID $reportedCorePid."
      }
      # Native readiness is an actual bearer-authenticated HTTP check. Also assert
      # independently that the same owned service rejects an unauthenticated caller.
      $handler = [System.Net.Http.HttpClientHandler]::new()
      $handler.UseProxy = $false
      $client = [System.Net.Http.HttpClient]::new($handler)
      $client.Timeout = [TimeSpan]::FromSeconds(3)
      try {
        $response = $client.GetAsync("http://127.0.0.1:42800/health").GetAwaiter().GetResult()
        try {
          if ([int]$response.StatusCode -ne 401) { Fail-Kat "authenticated-readiness" "Owned Core did not reject unauthenticated health (HTTP $([int]$response.StatusCode))." }
        } finally { $response.Dispose() }
      } finally { $client.Dispose() }
      if ($process.MainWindowHandle -ne 0) {
        Write-Output "Evidence: desktop_pid=$($process.Id), window=$($process.MainWindowHandle), core_pid=$reportedCorePid, authenticated health passed, unauthenticated health=401, owned listener=42800."
        return
      }
    }
  } while ((Get-Date) -lt $deadline)
  if ($process.MainWindowHandle -eq 0) { Fail-Kat "window-creation" "Desktop is alive but no main window appeared within $TimeoutSeconds seconds." }
  if ($script:children.Count -eq 0) { Fail-Kat "core-child-startup" "Window exists but there is no owned Core child." }
  Fail-Kat "authenticated-readiness" "Window and owned child exist, but native authenticated readiness evidence is absent."
}

function Assert-KatStopped($owned) {
  $deadline = (Get-Date).AddSeconds(8)
  do {
    $alive = @($owned | Where-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
    $listeners = @(Get-KatListener)
    if ($alive.Count -eq 0 -and $listeners.Count -eq 0) { return }
    Start-Sleep -Milliseconds 250
  } while ((Get-Date) -lt $deadline)
  Fail-Kat "port-lifecycle" "Shutdown left Core PIDs $(@($alive | ForEach-Object { $_.ProcessId }) -join ',') or listeners $(@($listeners | ForEach-Object { $_.OwningProcess }) -join ',')."
}

function Save-Diagnostics {
  # Never dump environment variables, bearer tokens, or command-line arguments.
  Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('kat-desktop.exe', 'kat-core.exe', 'msedgewebview2.exe') } |
    Select-Object Name, ProcessId, ParentProcessId, ExecutablePath |
    ConvertTo-Json -Depth 3 | Set-Content (Join-Path $DiagnosticsDirectory 'processes.json')
  @(Get-KatListener) | Select-Object LocalAddress, LocalPort, OwningProcess, State |
    ConvertTo-Json | Set-Content (Join-Path $DiagnosticsDirectory 'listeners.json')
  if (Test-Path $logs) {
    foreach ($file in Get-ChildItem $logs -Filter '*.log') {
      $tail = @(Get-Content $file.FullName -Tail 100)
      $safe = ($tail -join "`n") -replace '(?i)Bearer\s+\S+', 'Bearer [REDACTED]' -replace '\bsk-[A-Za-z0-9_-]+', '[REDACTED]'
      $safe | Set-Content (Join-Path $DiagnosticsDirectory $file.Name)
      Write-Output "--- $($file.Name) ---"
      Write-Output $safe
      # API-visible annotations remain available when a cloud log-download host is blocked.
      if ($env:GITHUB_ACTIONS -eq 'true') {
        $annotation = $safe.Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
        Write-Output "::notice title=KAT $($file.Name)::$annotation"
      }
    }
  }
}

try {
  if (-not (Test-Path $Executable)) { Fail-Kat 'desktop-process' "Desktop executable not found: $Executable" }
  if (@(Get-KatListener).Count -gt 0) { Fail-Kat 'port-lifecycle' 'Port 42800 is already occupied before launch; no existing process will be killed.' }
  foreach ($mode in @('normal-close', 'forced-termination')) {
    $startedMilliseconds = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $app = Start-Process -FilePath $Executable -PassThru
    Wait-KatReady $app
    Write-Output "PASS: packaged desktop window and authenticated owned Core startup ($mode)."
    if ($mode -eq 'normal-close') {
      if (-not $app.CloseMainWindow()) { Fail-Kat 'window-creation' 'Could not request normal window close.' }
    } else { Stop-Process -Id $app.Id -Force }
    if (-not $app.WaitForExit(15000)) { Fail-Kat 'desktop-process' "Desktop did not exit after $mode." }
    if ($mode -eq 'normal-close' -and $app.ExitCode -ne 0) { Fail-Kat 'desktop-process' "Normal close returned exit $($app.ExitCode)." }
    Assert-KatStopped $children
    Write-Output "PASS: $mode stopped owned Core and released port 42800."
  }
  Save-Diagnostics
} catch {
  $failure = $_
  Write-Output "FAIL: $failure"
  Save-Diagnostics
  throw $failure
} finally {
  if ($app) {
    $app.Refresh()
    if (-not $app.HasExited) { Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue }
  }
  foreach ($child in $children) { Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue }
}
