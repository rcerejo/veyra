$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$node = if ($nodeCommand) { $nodeCommand.Source } else {
    Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
}
$vite = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
$logs = Join-Path $projectRoot 'logs'
$runtimeFile = Join-Path $projectRoot '.veyra-runtime.json'

foreach ($required in @($python, $node, $vite)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required runtime file not found: $required"
    }
}

New-Item -ItemType Directory -Path $logs -Force | Out-Null

$backendListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($backendListener) {
    $backendPid = $backendListener.OwningProcess
} else {
    $backendProcess = Start-Process -FilePath $python `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
        -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logs 'backend.out.log') `
        -RedirectStandardError (Join-Path $logs 'backend.err.log')
    $backendPid = $backendProcess.Id
}

$frontendListener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($frontendListener) {
    $frontendPid = $frontendListener.OwningProcess
} else {
    $frontendProcess = Start-Process -FilePath $node -ArgumentList $vite, '--host', '127.0.0.1', '--port', '5173' `
        -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logs 'frontend.out.log') `
        -RedirectStandardError (Join-Path $logs 'frontend.err.log')
    $frontendPid = $frontendProcess.Id
}

$deadline = (Get-Date).AddSeconds(20)
do {
    try {
        $backendReady = (Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2).status -in @('ok', 'degraded')
        $frontendReady = (Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    } catch {
        $backendReady = $false
        $frontendReady = $false
    }
    if (-not ($backendReady -and $frontendReady)) { Start-Sleep -Milliseconds 500 }
} until (($backendReady -and $frontendReady) -or (Get-Date) -ge $deadline)

if (-not ($backendReady -and $frontendReady)) {
    throw "VEYRA did not become ready. Check logs in $logs"
}

# Virtual-environment launchers can hand off to a child process on Windows.
# Record the actual listener owners rather than the initial launcher PIDs.
$backendPid = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop).OwningProcess
$frontendPid = (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction Stop).OwningProcess
@{ backendPid = $backendPid; frontendPid = $frontendPid } | ConvertTo-Json | Set-Content -LiteralPath $runtimeFile -Encoding utf8

Write-Host 'VEYRA is running at http://127.0.0.1:5173/' -ForegroundColor Green

