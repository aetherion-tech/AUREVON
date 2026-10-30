param(
    [ValidateSet('Check','Setup','Build','Run','Backup','Restore','Audit')]
    [string]$Action = 'Check',
    [string]$Source,
    [string]$Target
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
function Checked-Native {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program (exit $LASTEXITCODE)" }
}
Push-Location $backendRoot
try {
    switch ($Action) {
        Setup {
            Checked-Native 'uv' @('sync','--locked')
            Push-Location $frontendRoot
            try { Checked-Native 'npm.cmd' @('ci') } finally { Pop-Location }
            Write-Output 'Dependencies ready. Existing .env, database, TLS and broker secrets preserved. No migration or service activation performed.'
        }
        Build {
            Push-Location $frontendRoot
            try { Checked-Native 'npm.cmd' @('run','build') } finally { Pop-Location }
        }
        Run { Checked-Native $pythonPath @('-m','app.tools.serve') }
        Check { Checked-Native $pythonPath @('-m','app.tools.local_ui_readiness') }
        Backup {
            if (!$Source -or !$Target) { throw 'Specify -Source database and -Target NEW backup file' }
            Checked-Native $pythonPath @('-m','app.tools.backup','backup',$Source,$Target)
        }
        Restore {
            if (!$Source -or !$Target) { throw 'Specify -Source backup and -Target NEW isolated database; existing files are refused' }
            Checked-Native $pythonPath @('-m','app.tools.backup','restore',$Source,$Target)
        }
        Audit {
            Checked-Native $pythonPath @('-m','app.tools.dependency_audit')
        }
    }
} finally { Pop-Location }
