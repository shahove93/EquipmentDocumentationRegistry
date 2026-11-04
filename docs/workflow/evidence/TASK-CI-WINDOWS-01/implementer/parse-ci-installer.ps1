# PowerShell 5.1 parser check for packaging/windows/ci-installer.ps1.
# Run with: powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <this file>
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../../../..')).Path
$target = Join-Path $repo 'packaging/windows/ci-installer.ps1'
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($target, [ref]$null, [ref]$errors) | Out-Null
if ($errors -and $errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Output $_.Message }
    Write-Output "PARSE_ERRORS=$($errors.Count)"
    exit 1
}
Write-Output 'PARSER_OK errors=0'
exit 0
