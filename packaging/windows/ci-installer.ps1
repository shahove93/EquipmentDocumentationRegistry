# CI-only driver: silently install the built EDR installer on an ephemeral
# GitHub-hosted Windows runner and exercise the installed runtime.
#
# The fail-closed guard below runs before any directory creation, install or
# process start. This script must never run on a developer host, a local VM or
# inside Windows Sandbox: those lifecycle checks stay manual.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string]$WorkDirectory = (Join-Path $env:TEMP 'edr-ci-work'),
    [string]$InstallDirectory = (Join-Path $env:TEMP 'edr-ci-install')
)
$ErrorActionPreference = 'Stop'

# ---- fail-closed guard (no side effects before this block succeeds) ----
$guardIssues = New-Object System.Collections.Generic.List[string]
if ($env:GITHUB_ACTIONS -ne 'true') { $guardIssues.Add('GITHUB_ACTIONS must be exactly true') }
if ($env:CI -ne 'true') { $guardIssues.Add('CI must be exactly true') }
if ($env:RUNNER_OS -ne 'Windows') { $guardIssues.Add('RUNNER_OS must be exactly Windows') }
if ($env:RUNNER_ENVIRONMENT -ne 'github-hosted') { $guardIssues.Add('RUNNER_ENVIRONMENT must be exactly github-hosted') }
$computerName = [string]$env:COMPUTERNAME
if ($computerName -ieq 'EDR-Win11-Test') {
    $guardIssues.Add("host name is the developer test machine: $computerName")
}
if ($computerName -like 'WDAG*') {
    $guardIssues.Add("Windows Sandbox host name is not allowed: $computerName")
}
try {
    $identityName = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ($identityName -like '*\WDAGUtilityAccount') {
        $guardIssues.Add("Windows Sandbox account is not allowed: $identityName")
    }
} catch {
    $guardIssues.Add("cannot determine the current Windows identity: $($_.Exception.Message)")
}
if ([string]::IsNullOrWhiteSpace($env:ProgramData)) {
    $guardIssues.Add('ProgramData is not defined')
}
$programDataRoot = if ([string]::IsNullOrWhiteSpace($env:ProgramData)) { $null } else { Join-Path $env:ProgramData 'EDR' }
foreach ($requiredAbsent in @($WorkDirectory, $InstallDirectory, $programDataRoot)) {
    if ($requiredAbsent -and (Test-Path -LiteralPath $requiredAbsent)) {
        $guardIssues.Add("path must be absent before install: $requiredAbsent")
    }
}
if (!$Exe -or !(Test-Path -LiteralPath $Exe -PathType Leaf)) {
    $guardIssues.Add("built installer EXE is missing: $Exe")
}
if ($guardIssues.Count -gt 0) {
    foreach ($issue in $guardIssues) {
        [Console]::Error.WriteLine("ci-installer guard failed: $issue")
    }
    exit 2
}
# ---- end guard ----

$work = [IO.Path]::GetFullPath($WorkDirectory)
$install = [IO.Path]::GetFullPath($InstallDirectory)
$installer = [IO.Path]::GetFullPath($Exe)
New-Item -ItemType Directory -Path $work | Out-Null

function Copy-EdrLogs {
    param([string]$Destination)
    $source = Join-Path $env:ProgramData 'EDR\state\data\logs'
    if (!(Test-Path -LiteralPath $source -PathType Container)) { return }
    $target = Join-Path $Destination 'logs'
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Get-ChildItem -LiteralPath $source -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force -ErrorAction SilentlyContinue
    }
}

$runtimeExit = 1
try {
    $installLog = Join-Path $work 'install.log'
    $setup = Start-Process -FilePath $installer -Wait -PassThru -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
        ('/DIR="' + $install + '"'), ('/LOG="' + $installLog + '"')
    )
    if ($setup.ExitCode -ne 0) {
        throw "Silent install failed with exit code $($setup.ExitCode); see $installLog"
    }
    Write-Output "Silent install succeeded: $installer -> $install"

    $installedFiles = @(
        (Join-Path $install 'python\python.exe'),
        (Join-Path $install 'launcher.ps1'),
        (Join-Path $install 'alembic.ini'),
        (Join-Path $install 'ui\index.html'),
        (Join-Path $env:ProgramData 'EDR\runtime\postgresql\bin\postgres.exe')
    )
    foreach ($path in $installedFiles) {
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required installed file is missing: $path"
        }
        Write-Output "Installed file present: $path"
    }

    $repo = (Resolve-Path "$PSScriptRoot/../..").Path
    $driver = Join-Path $repo 'packaging\windows\ci-installer.py'
    if (!(Test-Path -LiteralPath $driver -PathType Leaf)) {
        throw "CI runtime driver is missing: $driver"
    }
    $installedPython = Join-Path $install 'python\python.exe'
    & $installedPython -B $driver --install $install --work $work
    $runtimeExit = $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine("ci-installer failed: $($_.Exception.Message)")
    $runtimeExit = 1
} finally {
    Copy-EdrLogs -Destination $work
}
exit $runtimeExit
