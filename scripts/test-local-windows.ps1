param([string]$Executable = '', [string]$Model = 'qwen2.5:7b', [switch]$FilesOnly, [switch]$UiOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($UiOnly -and (-not $Executable -or $FilesOnly)) { throw 'UI-only diagnosis requires an executable and cannot use FilesOnly.' }
$repo = Split-Path -Parent $PSScriptRoot
$root = Join-Path $repo '.local/ollama-test'
$python = Join-Path $repo 'core/.venv/Scripts/python.exe'
$zip = Join-Path $root 'ollama.zip'
New-Item -ItemType Directory -Force -Path $root | Out-Null
# Explicit test dependency download, never part of installing or starting KAT.
# Official upstream release asset digest, not an unverified install script.
$url = 'https://github.com/ollama/ollama/releases/download/v0.40.1/ollama-windows-amd64.zip'
$sha256 = 'b394d14436d38032f23190e3f14eb2c6dad5ebbe4e192414f74c8fdca01703ab'
Write-Output "Downloading Ollama 0.40.1 (~1.47 GB) and $Model for explicit real-inference tests."
Invoke-WebRequest -Uri $url -OutFile $zip
if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha256) { throw 'Official Ollama asset checksum mismatch.' }
Expand-Archive $zip -DestinationPath (Join-Path $root 'runtime') -Force
$ollama = Join-Path $root 'runtime/ollama.exe'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $root 'models'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_DEBUG = 'false'
if (@(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue).Count -gt 0) { throw 'Ollama test port already occupied; no existing backend will be killed.' }
$server = $null
try {
  $server = Start-Process $ollama -ArgumentList 'serve' -PassThru -RedirectStandardOutput (Join-Path $root 'server.stdout.log') -RedirectStandardError (Join-Path $root 'server.stderr.log')
  $deadline = (Get-Date).AddSeconds(30)
  do {
    if ($server.HasExited) { throw 'Ollama test backend exited during startup.' }
    try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version'; break } catch { Start-Sleep -Milliseconds 300 }
  } while ((Get-Date) -lt $deadline)
  $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version'
  & $ollama pull $Model
  if ($LASTEXITCODE -ne 0) { throw 'Explicit Ollama test-model pull failed.' }
  if (-not $UiOnly) {
    $smokeArgs = @('--model', $Model)
    if ($FilesOnly) { $smokeArgs += '--files-only' }
    & $python (Join-Path $PSScriptRoot 'smoke-local.py') @smokeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Actual local Core inference/tools smoke failed.' }
  }
  if ($Executable) {
    & $python (Join-Path $PSScriptRoot 'smoke-installed-ui.py') --executable $Executable --model $Model
    if ($LASTEXITCODE -ne 0) { throw 'Actual installed desktop/local inference smoke failed.' }
  }
} catch {
  # Backend error logs contain server diagnostics; no chat bodies are logged at INFO.
  if (Test-Path (Join-Path $root 'server.stderr.log')) { Get-Content (Join-Path $root 'server.stderr.log') -Tail 60 }
  $logs = Join-Path $env:LOCALAPPDATA 'com.kat.assistant/logs'
  if (Test-Path $logs) {
    foreach ($file in Get-ChildItem $logs -Filter '*.log') {
      $safe = ((Get-Content $file.FullName -Tail 80) -join "`n") -replace '(?i)Bearer\s+\S+', 'Bearer [REDACTED]' -replace '\bsk-[A-Za-z0-9_-]+', '[REDACTED]'
      Write-Output "KAT $($file.Name):"
      Write-Output $safe
    }
  }
  throw
} finally {
  if ($server -and -not $server.HasExited) { & taskkill.exe /PID $server.Id /T /F | Out-Null }
}
