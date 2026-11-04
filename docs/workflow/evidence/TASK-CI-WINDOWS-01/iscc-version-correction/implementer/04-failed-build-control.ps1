# Failed-build control: simulates build.ps1 native failure with try/catch-rethrow.
# The version-check marker must never be reached and the step must exit non-zero.
$ErrorActionPreference = 'Stop'
$logDir = Join-Path $env:TEMP ('iscc-failed-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $logDir | Out-Null
$buildLog = Join-Path $logDir 'build.log'

try {
    & cmd.exe /c "exit 7"
    if ($LASTEXITCODE -ne 0) {
        throw "native command failed with exit code $LASTEXITCODE"
    }
    # This marker would only print if the native failure were swallowed.
    Write-Output "MARKER_VERSION_CHECK_REACHED"
} catch {
    $_ | Out-String | Add-Content -LiteralPath $buildLog
    throw
}
# The real workflow's log-existence + Select-String version check sits here.
Write-Output "MARKER_VERSION_CHECK_REACHED_AFTER_CATCH"
