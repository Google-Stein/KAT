# Run with pwsh on any platform. Exercise failure classification without launching
# a desktop, opening a port, or requiring Windows CIM/network cmdlets.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$path = Join-Path $PSScriptRoot '../../scripts/smoke-windows.ps1'
$tokens = $null
$errors = $null
$tree = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $path), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw "Smoke script syntax errors: $errors" }
foreach ($definition in $tree.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
  . ([scriptblock]::Create($definition.Extent.Text))
}
function Get-CimInstance { param($Filter, $ClassName) $script:mockChildren }
function Get-StartupEvidence { param($process) $script:mockEvidence }
function Get-KatListener { $script:mockListeners }
$TimeoutSeconds = 0
$children = @()
$mockChildren = @()
$mockEvidence = @()
$mockListeners = @()
$process = [pscustomobject]@{ Id = 42; HasExited = $false; ExitCode = 7; MainWindowHandle = 10 }
$process | Add-Member ScriptMethod Refresh { }
function Assert-Failure([string]$Category) {
  try { Wait-KatReady $process } catch {
    if (-not $_.Exception.Message.StartsWith("[$Category]")) { throw "Expected $Category; received $_" }
    Write-Output "PASS diagnostic: $Category"
    return
  }
  throw "Expected failure category $Category"
}
$process.HasExited = $true
Assert-Failure 'desktop-process'
$process.HasExited = $false
$mockEvidence = @('stage=core_failed Could not launch KAT Core')
Assert-Failure 'core-child-startup'
$mockEvidence = @('stage=core_failed local service rejected the owned credential. Another process may have claimed its port.')
Assert-Failure 'authenticated-readiness'
$mockEvidence = @('stage=core_failed Cannot use 127.0.0.1:42800')
Assert-Failure 'port-lifecycle'
$mockEvidence = @('stage=window_failed WebView unavailable')
Assert-Failure 'window-creation'
$mockEvidence = @()
$mockChildren = @([pscustomobject]@{Name='kat-core.exe'; ProcessId=11}, [pscustomobject]@{Name='kat-core.exe'; ProcessId=12})
Assert-Failure 'process-topology'
$mockChildren = @([pscustomobject]@{Name='kat-core.exe'; ProcessId=11})
$mockEvidence = @('stage=core_ready core_pid=12 authenticated=true port=42800')
Assert-Failure 'process-topology'
$mockEvidence = @('stage=core_ready core_pid=11 authenticated=true port=42800')
$mockListeners = @([pscustomobject]@{OwningProcess=12})
Assert-Failure 'port-lifecycle'
$mockEvidence = @()
$mockChildren = @()
Assert-Failure 'core-child-startup'
$mockChildren = @([pscustomobject]@{Name='kat-core.exe'; ProcessId=11})
Assert-Failure 'authenticated-readiness'
$process.MainWindowHandle = 0
Assert-Failure 'window-creation'
$process.MainWindowHandle = 10
$mockEvidence = @('stage=core_ready core_pid=11 authenticated=true port=42800')
$mockListeners = @([pscustomobject]@{OwningProcess=11})
$process.MainWindowHandle = 0
function Get-KatUnauthenticatedStatus { throw 'Probe must wait for window creation.' }
Assert-Failure 'window-creation'
$process.MainWindowHandle = 10
$mockEvidence += 'stage=window_creating WebView2 initialization'
Assert-Failure 'window-creation'
Write-Output 'PASS diagnostic: Win32 handle alone does not establish completed WebView initialization'
$mockEvidence += 'stage=window_ready native window created'
$probeAttempts = 0
function Get-KatUnauthenticatedStatus { $script:probeAttempts++; if ($script:probeAttempts -eq 1) { 0 } else { 401 } }
$TimeoutSeconds = 3
Wait-KatReady $process
if ($probeAttempts -ne 2) { throw 'Transient probe was not retried before readiness.' }
Write-Output 'PASS diagnostic: transient independent probe retried within original deadline'
$TimeoutSeconds = 0
function Get-KatUnauthenticatedStatus { 0 }
Assert-Failure 'authenticated-readiness'
function Get-KatUnauthenticatedStatus { 200 }
Assert-Failure 'authenticated-readiness'
$wrapped = [InvalidOperationException]::new('wrapper', [TimeoutException]::new('synthetic timeout'))
if (-not (Test-KatTransientProbeError $wrapped)) { throw 'Wrapped timeout not recognized.' }
if (Test-KatTransientProbeError ([InvalidOperationException]::new('unexpected'))) { throw 'Unexpected error was hidden as transient.' }
Write-Output 'PASS diagnostic: transient probe errors classified without hiding unrelated failures'
$mockListeners = @()
Assert-KatStopped @()
Write-Output 'PASS diagnostic: clean lifecycle returns'
function Get-Process { param($Id, $ErrorAction) [pscustomobject]@{ Id = $Id } }
$clockTick = 0
function Get-Date { $script:clockTick++; [DateTime]::UtcNow.AddSeconds($script:clockTick * 10) }
try { Assert-KatStopped @([pscustomobject]@{ProcessId=11}) } catch {
  if (-not $_.Exception.Message.StartsWith('[port-lifecycle]')) { throw }
  Write-Output 'PASS diagnostic: leaked Core detected after close'
  $leakDetected = $true
}
if (-not (Get-Variable leakDetected -ErrorAction SilentlyContinue)) { throw 'Leaked Core was not detected' }
