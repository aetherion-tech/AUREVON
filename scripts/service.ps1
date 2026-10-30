param([ValidateSet('Inspect','Install','Start','Stop','Restart','Remove','ConfigureRecovery')][string]$Action = 'Inspect')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
Push-Location (Join-Path $projectRoot 'backend')
try {
    if ($Action -eq 'Inspect') {
        Get-Service -Name AUREVONPaper -ErrorAction SilentlyContinue
        return
    }
    if ($Action -eq 'ConfigureRecovery') {
        # Explicit operation only, after identity/TLS/DPAPI/lifecycle verification.
        & sc.exe config AUREVONPaper start= delayed-auto
        if ($LASTEXITCODE -ne 0) { throw 'Cannot configure SCM startup' }
        & sc.exe failure AUREVONPaper reset= 86400 actions= restart/10000/restart/30000/restart/60000
        if ($LASTEXITCODE -ne 0) { throw 'Cannot configure SCM failure recovery' }
        & sc.exe failureflag AUREVONPaper 1
        if ($LASTEXITCODE -ne 0) { throw 'Cannot configure SCM recovery flag' }
        return
    }
    $serviceAction = switch ($Action) {
        Install { 'install' }; Start { 'start' }; Stop { 'stop' }
        Restart { 'restart' }; Remove { 'remove' }
    }
    if ($Action -eq 'Install') {
        & $pythonPath aurevon_service.py --startup manual install
    } else {
        & $pythonPath aurevon_service.py $serviceAction
    }
    if ($LASTEXITCODE -ne 0) { throw 'SCM action failed; use the same Windows identity as local DPAPI/TLS or configure its permissions explicitly.' }
} finally { Pop-Location }
