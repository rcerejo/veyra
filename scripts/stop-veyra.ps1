$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeFile = Join-Path $projectRoot '.veyra-runtime.json'

if (-not (Test-Path -LiteralPath $runtimeFile)) {
    Write-Host 'No VEYRA runtime record was found.'
    exit 0
}

$runtime = Get-Content -Raw -LiteralPath $runtimeFile | ConvertFrom-Json
foreach ($entry in @(@{ Port = 8000; Pid = $runtime.backendPid }, @{ Port = 5173; Pid = $runtime.frontendPid })) {
    $listener = Get-NetTCPConnection -LocalPort $entry.Port -State Listen -ErrorAction SilentlyContinue
    if ($listener -and $listener.OwningProcess -eq $entry.Pid) {
        Stop-Process -Id $entry.Pid -Force
        Write-Host "Stopped VEYRA service on port $($entry.Port)."
    }
}

Remove-Item -LiteralPath $runtimeFile -Force

