# Positive/negative proof of the exact compiler-version signal (read-only).
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..\..')).Path
$pattern = '^Compiler engine version: Inno Setup 6\.7\.3$'

$realLog = Join-Path $root 'docs/workflow/evidence/TASK-WINDOWS-CRT-OFFLINE-01/build.log'
if (!(Test-Path -LiteralPath $realLog -PathType Leaf)) {
    throw "Real build log not found: $realLog"
}
$positive = Select-String -LiteralPath $realLog -Pattern $pattern -Quiet
Write-Output "positive_real_6.7.3=$positive ($realLog)"

$tmp = Join-Path $env:TEMP ('iscc-signal-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $log674 = Join-Path $tmp 'build-6.7.4.log'
    Set-Content -LiteralPath $log674 -Value 'Compiler engine version: Inno Setup 6.7.4' -Encoding ascii
    $negative674 = Select-String -LiteralPath $log674 -Pattern $pattern -Quiet
    Write-Output "negative_synthetic_6.7.4=$negative674 ($log674)"

    $logMissing = Join-Path $tmp 'build-missing.log'
    Set-Content -LiteralPath $logMissing -Value "some unrelated build output`r`nDone." -Encoding ascii
    $negativeMissing = Select-String -LiteralPath $logMissing -Pattern $pattern -Quiet
    Write-Output "negative_missing_line=$negativeMissing ($logMissing)"
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force
}

if (-not $positive) { throw "Positive control failed: real 6.7.3 log did not match" }
if ($negative674) { throw "Negative control failed: 6.7.4 log matched" }
if ($negativeMissing) { throw "Negative control failed: missing-line log matched" }
Write-Output "RESULT=PASS"
