[CmdletBinding()]
param(
    # Build with ISCC /DSmokeBuild to use a different uninstall registry identity.
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$WorkDirectory
)
$ErrorActionPreference = 'Stop'
$work = [IO.Path]::GetFullPath($WorkDirectory)
if (Test-Path -LiteralPath $work) { throw 'Use a fresh smoke directory; existing data must be preserved' }
New-Item -ItemType Directory -Path $work | Out-Null
$installPath = "$work/application"
$previousLocalAppData = $env:LOCALAPPDATA
try {
    $env:LOCALAPPDATA = "$work/profile"
    . "$PSScriptRoot/launcher.ps1"
    if (!(Test-EdrCrt)) { throw 'Host CRT prerequisite is not available' }
    if (Test-EdrCrt -Directory "$work/nonexistent-crt") { throw 'Missing CRT incorrectly detected as present' }
    if ((Get-EdrCrtMessage) -notmatch 'https://learn.microsoft.com/') { throw 'Official prerequisite URL is missing' }
    $missing = Start-Process -FilePath $Installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
        '/EDRTestMissingCRT=1',('/DIR="' + "$work/missing-runtime-install" + '"'),('/LOG="' + "$work/missing-runtime.log" + '"')) -WindowStyle Hidden -Wait -PassThru
    if (!$missing.ExitCode -or (Test-Path -LiteralPath "$work/missing-runtime-install")) {
        throw 'Absent-runtime preflight must refuse installation before writing payload'
    }
    $group = 'EDR-Smoke-' + [IO.Path]::GetFileName($work)
    $setup = Start-Process -FilePath $Installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
        ('/DIR="' + $installPath + '"'),('/GROUP="' + $group + '"'),'/TASKS=',('/LOG="' + "$work/install.log" + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($setup.ExitCode) { throw "Install failed: $($setup.ExitCode)" }
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:APPDATA/Microsoft/Windows/Start Menu/Programs/$group/EDR.lnk")
    if ($shortcut.TargetPath -notlike '*powershell.exe' -or $shortcut.Arguments -notlike '*launcher.ps1*start') {
        throw 'Installed launcher shortcut is invalid'
    }
    @{ missingRuntimeExit=$missing.ExitCode; hostRuntimePresent=$true; syntheticAbsentRuntime=$true;
       shortcutTarget=$shortcut.TargetPath; shortcutArguments=$shortcut.Arguments } |
        ConvertTo-Json | Set-Content -LiteralPath "$work/preflight.json" -Encoding utf8
    New-Item -ItemType Directory -Path "$work/driver" | Out-Null
    Copy-Item -LiteralPath "$installPath/python" -Destination "$work/driver/python" -Recurse
    try {
        $ErrorActionPreference = 'Continue'
        # The test driver must not hold installed DLLs open during update/uninstall.
        & "$work/driver/python/python.exe" -B "$PSScriptRoot/smoke.py" --install $installPath --work $work --installer $Installer
        $runtimeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = 'Stop' }
    if ($runtimeExit) { throw "Runtime smoke failed: $runtimeExit" }
    Write-Output "HOST_NATIVE_SMOKE succeeded; clean Windows VM remains a separate check. Artifacts: $work"
} finally {
    $env:LOCALAPPDATA = $previousLocalAppData
}
