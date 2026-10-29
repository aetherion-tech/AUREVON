$ErrorActionPreference = 'Stop'
$frontendDirectory = Split-Path -Parent $PSScriptRoot
$projectDirectory = Split-Path -Parent $frontendDirectory
$pythonExecutable = Join-Path $projectDirectory 'backend/.venv/Scripts/python.exe'
& $pythonExecutable (Join-Path $PSScriptRoot 'local_tls.py')
if ($LASTEXITCODE -ne 0) { throw 'Local certificate generation failed.' }
$tlsDirectory = Join-Path $frontendDirectory '.local-tls'
$userSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $tlsDirectory /inheritance:r /grant:r "*${userSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict access to local certificate files.' }
$certificatePath = Join-Path $tlsDirectory 'localhost-cert.cer'
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($certificatePath)
$trustedPath = 'Cert:\CurrentUser\Root\' + $certificate.Thumbprint
if (-not (Test-Path $trustedPath)) {
    Import-Certificate -FilePath $certificatePath -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null
}
if (-not (Test-Path $trustedPath)) { throw 'Windows user trust installation was not completed.' }
Write-Output "Trusted local dashboard certificate: $($certificate.Thumbprint)"
Write-Output 'Run npm.cmd run dev, then open https://127.0.0.1:5173/dashboard/'
