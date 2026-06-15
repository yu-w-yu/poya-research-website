$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$stdout = Join-Path $root "server.out.log"
$stderr = Join-Path $root "server.err.log"

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -like "python*" -and $_.CommandLine -match "server\.py" }

foreach ($process in $running) {
    Stop-Process -Id $process.ProcessId -Force
}

Start-Process `
    -FilePath $python `
    -ArgumentList ".\server.py" `
    -WorkingDirectory $root `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden

Start-Sleep -Seconds 2
$health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8765/health" -TimeoutSec 5
Write-Output "POYA research website is running: http://127.0.0.1:8765"
Write-Output "Health: $($health.StatusCode) $($health.Content)"
