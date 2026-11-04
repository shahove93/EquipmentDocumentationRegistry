# Stale-log control: the retained $logDir freshness guard rejects a pre-existing log.
$ErrorActionPreference = 'Stop'
$logDir = Join-Path $env:TEMP ('iscc-stale-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $logDir | Out-Null
$buildLog = Join-Path $logDir 'build.log'
Set-Content -LiteralPath $buildLog -Value 'Compiler engine version: Inno Setup 6.7.3' -Encoding ascii
Write-Output "stale_log_pre_exists=$(Test-Path -LiteralPath $buildLog -PathType Leaf)"

if (Test-Path -LiteralPath $logDir) {
    throw "Build log directory must be fresh: $logDir"
}
Write-Output "MARKER_GUARD_BYPASSED"
